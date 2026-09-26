# builtins
from unittest import TestCase
from unittest.mock import patch

# modules
from src.resources.pod_manager import PodManager


class TestPollTermination(TestCase):
    '''
    Regression test for a real bug (fixed 2026-09-26): poll_termination used `timeout_seconds` as
    the SLEEP DURATION between checks instead of an overall deadline (every sibling poll_*/get_*
    method in this class treats it as a real deadline with a 1s poll interval) - a pod that was
    already gone by the very first check still had to wait out a second full `timeout_seconds`
    sleep before the loop noticed, and a pod that never terminates looped forever instead of
    raising TimeoutError like every sibling method does.
    '''

    def test_returns_immediately_once_pod_is_confirmed_gone(self) -> None:
        with patch.object(PodManager, "get", return_value={}) as mock_get, \
             patch("src.resources.pod_manager.time.sleep") as mock_sleep:
            PodManager.poll_termination("ns-1", "pod-1", timeout_seconds=20.0)

        mock_get.assert_called_once()
        mock_sleep.assert_not_called()

    def test_polls_at_a_short_fixed_interval_not_the_full_timeout(self) -> None:
        '''The actual bug: a pod gone on the SECOND check must not have slept a full
        `timeout_seconds` twice (~2x timeout_seconds wall time) to get there - it should sleep
        ~1s between checks regardless of how large timeout_seconds is.'''
        with patch.object(PodManager, "get", side_effect=[{"pod_name": "pod-1"}, {}]), \
             patch("src.resources.pod_manager.time.sleep") as mock_sleep:
            PodManager.poll_termination("ns-1", "pod-1", timeout_seconds=20.0)

        mock_sleep.assert_called_once_with(1)

    def test_raises_timeout_error_if_pod_never_terminates(self) -> None:
        with patch.object(PodManager, "get", return_value={"pod_name": "pod-1"}), \
             patch("src.resources.pod_manager.time.sleep"), \
             patch("src.resources.pod_manager.time.time", side_effect=[0, 1, 25]):
            with self.assertRaises(TimeoutError):
                PodManager.poll_termination("ns-1", "pod-1", timeout_seconds=20.0)
