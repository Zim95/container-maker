# builtins
from dataclasses import dataclass


@dataclass
class ListResourceDataClass:
    '''
    Base Data class for list a resource.
    '''
    pass


@dataclass
class GetResourceDataClass:
    '''
    Base Data class for getting a resource.
    '''
    pass


@dataclass
class CreateResourceDataClass:
    '''
    Base Data class for creating a resource.
    '''
    pass


@dataclass
class DeleteResourceDataClass:
    '''
    Base Data class for deleting a resource.
    '''
    pass


@dataclass
class SaveResourceDataClass:
    '''
    Base Data class for saving a resource. Only used in Pods.
    '''
    pass
