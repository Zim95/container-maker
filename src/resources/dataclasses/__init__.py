# builtins
from dataclasses import dataclass


@dataclass
class ListResourceDataClass:
    '''
    Base Data class for list a resource.
    '''
    pass

@dataclass
class CreateResourceDataClass:
    '''
    Base Data class for creating a resource.
    '''
    pass


@dataclass
class StartResourceDataClass:
    '''
    Base Data class for starting a resource.
    '''
    pass


@dataclass
class StopResourceDataClass:
    '''
    Base Data class for stoping a resource.
    '''
    pass


@dataclass
class DeleteResourceDataClass:
    '''
    Base Data class for deleting a resource.
    '''
    pass
