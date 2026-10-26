
"""
This tests rag.py

None of the tests here actually call Claude API. They are totally free, require no API key, 
and provide the same results every time.




"""




import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np 
import pytest

# Allows 'import rag' to work no matter where pytest gets launched from
sys.path.insert(0, str(Path(__file__).parent.parent))
import rag


### Create a fake stand-in for the Claude client
class FakeMessages: 
    
    def __init__(self): 
        self.calls = [] # hold every request our code gets here
        
    # A stand in for the real API all that does the following: 
    # 1) Using **kwargs we collect all passed arguments from our code sent to client like model=, max_tokens=,
    # system=, and messages= than we append them to self.calls so that we essentially have a running receipt of the calls
    # 2) Returns a lookalike response in message.content[0].text format
    def create(self, **kwargs): 
        self.calls.append(**kwargs)
        # Mimic the shape of an actual shape from a Claude client: message.content[0].text
        return SimpleNamespace(content=[SimpleNamespace(text="Fake Text")])
    
    
class FakeClient:
    
    def __init__(self): 
        self.messages = FakeMessages