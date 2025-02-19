from google.protobuf.message import Message
from typing import TypeVar
from abc import ABC, abstractmethod
from dataclasses import dataclass


T = TypeVar('T', bound=dataclass)


class InputDataTransformer(ABC):
    '''
    Transform protobuf message to dataclass
    '''
    @classmethod
    @abstractmethod
    def transform(cls, input_data: Message) -> T:
        '''
        Transform protobuf message to dataclass
        '''
        pass


class OutputDataTransformer(ABC):
    '''
    Transform dictionary to protobuf message
    '''
    @classmethod
    @abstractmethod
    def transform(cls, output_data: dict) -> Message:
        '''
        Transform dictionary to protobuf message
        '''
        pass
