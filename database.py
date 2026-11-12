"""
Root database module (re-exports from database/ package)
"""
from database.crud import *
from database.connection import init_connection, close_connection, IS_POSTGRES
