"""
This module was created to automate farming
process in browser strategy game TribalWars.
See "TribalWars Super.docx" design document for details.
"""
from threading import Lock
from request_manager import DummyRequestManager
from data_management import ReportBuilder

class Bot:

    def __init__(self):
        self.lock = Lock()
        self.request_manager = DummyRequestManager()
        self.report_builder = ReportBuilder(self.request_manager, self.lock)







     
 



        
        