# builtins
import threading
from concurrent.futures import ThreadPoolExecutor

# third party
import grpc
import click
from kubernetes.client.rest import ApiException

# modules
from src.grpc.servicer import ContainerMakerAPIServicerImpl
from src.grpc.request_id_interceptor import RequestIdInterceptor
from container_maker_spec.service_pb2_grpc import add_ContainerMakerAPIServicer_to_server
from src.common.utils import read_certs
from src.common.exceptions import UnsupportedRuntimeEnvironment
from src.common.logging_setup import configure_logging, get_logger
from src.resources.save_reconciler import run_loop as run_save_reconciler


# structured logging setup (JSON lines, matching browseterm-server)
configure_logging("container-maker")
logger = get_logger("app")


def serve(
    server_threads: int,
    address: str,
    port: int,
    use_ssl: bool,
) -> None:
    """
    Server function that propagates errors to clients
    """
    server = None
    try:
        # create server (RequestIdInterceptor threads the caller's x-request-id into logging)
        server = grpc.server(
            ThreadPoolExecutor(max_workers=server_threads),
            interceptors=[RequestIdInterceptor()]
        )

        # add container maker servicer implementation
        container_maker_servicer = ContainerMakerAPIServicerImpl()
        add_ContainerMakerAPIServicer_to_server(container_maker_servicer, server)

        # construct server_bind
        server_bind = f"{address}:{port}"

        # add secure/insecure channel
        if not use_ssl:
            server.add_insecure_port(server_bind)
        else:
            server_key = read_certs('SERVER_KEY', './cert/server.key')
            server_cert = read_certs('SERVER_CRT', './cert/server.crt')
            ca_cert = read_certs('CA_CRT', './cert/ca.crt')
            # P21 (~/browseterm/p.md's "P21" section, plan section 18: "Inspect whether current
            # gRPC setup truly enforces client authentication; do not call it mTLS unless
            # verified"): grpc.ssl_server_credentials' require_client_auth defaults to False.
            # Without it explicitly set True, root_certificates was accepted but never actually
            # used to REQUIRE/verify a client cert - any client could connect over plain
            # server-authenticated TLS with no client cert at all, despite the client side
            # (browseterm-server-local's grpc_utils.py) always presenting one. This was one-way
            # TLS, not mTLS, though CLIENT_KEY/CLIENT_CRT/CA_CRT were already wired end to end.
            credentials = grpc.ssl_server_credentials(
                [(server_key, server_cert)],
                root_certificates=ca_cert,
                require_client_auth=True,
            )
            server.add_secure_port(server_bind, credentials)

        # Any live container-maker replica can reconcile any stuck save on its next tick, so this
        # doesn't need to be the same pod/process that handled the original (now-dead) save
        # request -- daemon=True so it never blocks process shutdown.
        threading.Thread(target=run_save_reconciler, daemon=True, name="save-reconciler").start()

        server.start()
        logger.info(f"Server started {'with SSL' if use_ssl else ''} at: {address}:{port}")
        server.wait_for_termination()
    except TimeoutError as te:
        logger.error(f'TimeoutError: {str(te)}')
        raise grpc.RpcError(
            code=grpc.StatusCode.DEADLINE_EXCEEDED,
            details=f"Operation timed out: {str(te)}"
        )
    except ApiException as ae:
        logger.error(f'ApiException: {str(ae)}')
        raise grpc.RpcError(
            code=grpc.StatusCode.INTERNAL,
            details=f"Kubernetes API error: {str(ae)}"
        )
    except UnsupportedRuntimeEnvironment as ure:
        logger.error(f'UnsupportedRuntimeEnvironment: {str(ure)}')
        raise grpc.RpcError(
            code=grpc.StatusCode.FAILED_PRECONDITION,
            details=f"Unsupported runtime environment: {str(ure)}"
        )
    except Exception as e:
        logger.error(f'Error occurred: {str(e)}')
        raise grpc.RpcError(
            code=grpc.StatusCode.UNKNOWN,
            details=f"Unexpected error: {str(e)}"
        )
    except KeyboardInterrupt:
        logger.info("Received interrupt signal. Shutting down gracefully...")
        if server:
            server.stop(grace=5)  # give it 5 seconds to wrap up


@click.command()
@click.option("--server_threads", type=int, default=10, help="Number of threads to run the grpc server")
@click.option("--address", type=str, default="[::]", help="IP address of the grpc server")
@click.option("--port", type=int, default=50052, help="Port of the grpc server")
@click.option("--use_ssl", type=bool, default=False, help="Use SSL flag")
def main(
    server_threads: int,
    address: str,
    port: int,
    use_ssl: bool
) -> None:
    """
    Main command line handler.
    """
    serve(
        server_threads=server_threads,
        address=address,
        port=port,
        use_ssl=use_ssl,
    )


if __name__ == "__main__":
    main()
