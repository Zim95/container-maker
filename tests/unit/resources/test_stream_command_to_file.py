# builtins
import base64
import os
import tempfile
from unittest import TestCase
from unittest.mock import patch

# modules
from src.resources.pod_manager import ExecUtility


class _FakeStreamClient:
    '''
    Minimal stand-in for kubernetes.stream ws_client.WSClient.

    Serves a pre-split list of base64 stdout chunks, one per loop iteration, then reports
    closed. This lets us drive ExecUtility.stream_command_to_file without a real cluster and
    prove the incremental base64 decode is correct across arbitrary (non-4-aligned) chunk
    boundaries.
    '''

    def __init__(self, stdout_chunks: list) -> None:
        self._chunks: list = list(stdout_chunks)
        self.closed: bool = False

    def is_open(self) -> bool:
        return len(self._chunks) > 0

    def update(self, timeout=None) -> None:
        return None

    def peek_stdout(self) -> bool:
        return len(self._chunks) > 0

    def read_stdout(self) -> str:
        return self._chunks.pop(0)

    def peek_stderr(self) -> bool:
        return False

    def read_stderr(self) -> str:
        return ""

    def close(self) -> None:
        self.closed = True


def _split(text: str, sizes: list) -> list:
    '''Split text into chunks whose lengths cycle through `sizes` (to force odd boundaries).'''
    chunks: list = []
    i: int = 0
    j: int = 0
    while i < len(text):
        size = sizes[j % len(sizes)]
        chunks.append(text[i:i + size])
        i += size
        j += 1
    return chunks


class TestStreamCommandToFile(TestCase):
    '''
    Unit test for ExecUtility.stream_command_to_file.

    This is a UNIT test: no cluster. The kubernetes `stream` call and the client check are
    mocked. It guards the memory-bounded snapshot read used by MinIO save: base64 stdout is
    decoded incrementally and written to a local file, and the reconstructed bytes must exactly
    equal the original regardless of how the base64 stream is chunked.
    '''

    def setUp(self) -> None:
        print('Test: setUp TestStreamCommandToFile')
        # deterministic, non-trivial payload (~50 KB, all byte values) — no randomness needed
        self.original: bytes = bytes(range(256)) * 200
        self.b64_text: str = base64.b64encode(self.original).decode('ascii')

    def _run_with_chunks(self, chunks: list) -> bytes:
        fake = _FakeStreamClient(chunks)
        fd, tmp_path = tempfile.mkstemp(suffix='.bin')
        os.close(fd)
        try:
            with patch('src.resources.pod_manager.ExecUtility.check_kubernetes_client', return_value=None), \
                 patch('src.resources.pod_manager.stream', return_value=fake):
                written = ExecUtility.stream_command_to_file(
                    'pod', 'ns', 'pod', 'base64 -w 0 /snap.tar.gz', tmp_path,
                )
            with open(tmp_path, 'rb') as f:
                data = f.read()
            self.assertEqual(written, len(data))
            self.assertTrue(fake.closed)  # stream must always be closed
            return data
        finally:
            os.remove(tmp_path)

    def test_decodes_across_non_aligned_chunks(self) -> None:
        print('Test: test_decodes_across_non_aligned_chunks')
        # chunk sizes NOT multiples of 4 -> exercises the carry buffer on every boundary
        chunks = _split(self.b64_text, [7, 13, 4096, 3, 1])
        self.assertEqual(self._run_with_chunks(chunks), self.original)

    def test_decodes_single_chunk(self) -> None:
        print('Test: test_decodes_single_chunk')
        self.assertEqual(self._run_with_chunks([self.b64_text]), self.original)

    def test_tolerates_whitespace_in_stream(self) -> None:
        print('Test: test_tolerates_whitespace_in_stream')
        # a stray trailing newline (as a shell may emit) must not corrupt the decode
        chunks = _split(self.b64_text, [64]) + ['\n']
        self.assertEqual(self._run_with_chunks(chunks), self.original)
