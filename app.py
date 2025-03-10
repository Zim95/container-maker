# builtins
from concurrent.futures import ThreadPoolExecutor
import logging

# third party
import grpc
import click
from kubernetes.client.rest import ApiException

# modules
from src.grpc.servicer import ContainerMakerAPIServicerImpl
from container_maker_spec.service_pb2_grpc import add_ContainerMakerAPIServicer_to_server
from src.common.utils import read_certs
from src.common.exceptions import UnsupportedRuntimeEnvironment


# logger setup
logger: logging.Logger = logging.getLogger(__name__)
handler: logging.StreamHandler = logging.StreamHandler()
formatter: logging.Formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
logger.setLevel(logging.DEBUG)
handler.setLevel(logging.DEBUG)
handler.setFormatter(formatter)
logger.addHandler(handler)


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
        # create server
        server = grpc.server(
            ThreadPoolExecutor(max_workers=server_threads)
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
            credentials = grpc.ssl_server_credentials(
                [(server_key, server_cert)], 
                root_certificates=ca_cert
            )
            server.add_secure_port(server_bind, credentials)

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
    finally:
        if server:
            logger.info("Stopping server...")
            server.stop(grace=None)  # Immediate shutdown


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
