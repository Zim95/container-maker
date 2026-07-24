"""
gRPC server interceptor that threads the caller's correlation id into logging.

browseterm-server sends its per-request `request_id` as the `x-request-id` gRPC metadata key on
every call into container-maker (see containers_service.py). This interceptor reads that key at the
start of each RPC and seeds the logging contextvar via set_request_context, so every log line
emitted while handling the call carries the same request_id and a request's lifecycle can be
reconstructed across both services. If the header is absent, a fresh id is minted.
"""
import grpc

from src.common.logging_setup import set_request_context

# Metadata key browseterm-server uses to propagate the correlation id.
REQUEST_ID_METADATA_KEY = "x-request-id"


class RequestIdInterceptor(grpc.ServerInterceptor):
    """Read `x-request-id` from incoming metadata and set the per-request logging context."""

    def intercept_service(self, continuation, handler_call_details):
        metadata = dict(handler_call_details.invocation_metadata or ())
        request_id = metadata.get(REQUEST_ID_METADATA_KEY)
        # set_request_context mints a fresh id when request_id is None/empty.
        set_request_context(request_id=request_id)
        return continuation(handler_call_details)
