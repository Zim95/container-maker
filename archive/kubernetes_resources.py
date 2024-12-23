import abc


class KubernetesResourceManager:

    @abc.abstractmethod
    def create(self, metadata: dict) -> None:
        pass

    @abc.abstractmethod
    def get(self, metadata: dict) -> None:
        pass

    @abc.abstractmethod
    def delete(self, metadata: dict) -> None:
        pass


class PodManager:

    def create(self, metadata: dict) -> None:
        pass