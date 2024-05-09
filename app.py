# builtins
import concurrent.futures as futures

# third party
import grpc
import click

# modules
import src.servicer as servicer
from container_maker_spec.service_pb2_grpc import add_ContainerMakerAPIServicer_to_server


def serve(
    server_threads: int,
    address: str,
    port: int,
    use_ssl: bool,
) -> None:
    """
    Server function.

    Author: Namah Shrestha
    """
    # create server
    server: grpc.Server = grpc.server(
        futures.ThreadPoolExecutor(max_workers=server_threads)
    )

    # add container maker servicer implementation
    container_maker_servicer: servicer.ContainerMakerAPIServicer = servicer.ContainerMakerAPIServicerImpl()
    add_ContainerMakerAPIServicer_to_server(container_maker_servicer, server)

    # construct server_bind
    server_address: str = address if address else "[::]"
    server_port: int = port if port else 50051
    server_bind: str = f"{server_address}:{server_port}"

    # add secure/insecure channel
    if use_ssl:
        server.add_insecure_port(server_bind)
    else:
        server.add_secure_port(server_bind)

    # Run server
    try:
        server.start()
        server.wait_for_termination()
    except Exception:
        server.stop()


@click.command()
@click.option("--server_threads", type=int, default=10, help="Number of threads to run the grpc server")
@click.option("--address", type=str, required=False, help="IP address of the grpc server")
@click.option("--port", type=int, required=False, help="Port of the grpc server")
@click.option("--use_ssl", type=bool, default=False, help="Use SSL flag")
def main(
    server_threads: int,
    address: str,
    port: int,
    use_ssl: bool
) -> None:
    """
    Main command line handler.

    Author: Namah Shrestha
    """
    serve(
        server_threads=server_threads,
        address=address,
        port=port,
        use_ssl=use_ssl,
    )


if __name__ == "__main__":
    main()
