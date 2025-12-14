"""
Database Manager Unit Tests
"""
import unittest
from unittest.mock import MagicMock, patch
import os
import sys

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database.db_manager import DatabaseManager

class TestDatabaseManager(unittest.TestCase):
    
    def setUp(self):
        # Patch sqlite3
        self.sqlite_patcher = patch('backend.database.db_manager.sqlite3')
        self.mock_sqlite = self.sqlite_patcher.start()
        
        # Patch config
        self.config_patcher = patch('database.db_manager.config')
        self.mock_config = self.config_patcher.start()
        self.mock_config.DATABASE_MODE = "local"
        
        # Patch psycopg2 (if needed)
        self.psycopg2_patcher = patch('database.db_manager.psycopg2', create=True)
        self.mock_psycopg2 = self.psycopg2_patcher.start()
        
        # Initialize manager
        # We need to mock _init_database to avoid file operations
        with patch.object(DatabaseManager, '_init_database'):
            self.db_manager = DatabaseManager(db_path=":memory:")

    def tearDown(self):
        self.sqlite_patcher.stop()
        self.config_patcher.stop()
        self.psycopg2_patcher.stop()

    def test_get_connection_sqlite(self):
        """Test getting SQLite connection"""
        conn = self.db_manager.get_connection()
        self.mock_sqlite.connect.assert_called()
        self.assertEqual(conn, self.mock_sqlite.connect.return_value)

    def test_get_connection_postgres_direct(self):
        """Test getting PostgreSQL connection (direct)"""
        # Switch to cloud mode
        self.mock_config.DATABASE_MODE = "cloud"
        self.mock_config.DATABASE_URL = "postgres://user:pass@host:5432/db"
        
        # Mock psycopg2 availability
        with patch('database.db_manager.PSYCOPG2_AVAILABLE', True):
            # Re-init manager to pick up cloud mode
            # Mock _init_connection_pool to fail
            with patch.object(DatabaseManager, '_init_connection_pool') as mock_init_pool:
                # We need to simulate connection pool being None (which it is by default)
                # But we also need to ensure get_connection tries to use it
                
                # Create a new manager for this test
                db_manager = DatabaseManager()
                # Force connection pool to be None
                db_manager._connection_pool = None
                
                # Mock psycopg2.connect
                self.mock_psycopg2.connect.return_value = MagicMock()
                
                conn = db_manager.get_connection()
                
                # Should have fallen back to direct connect
                self.mock_psycopg2.connect.assert_called()

    def test_execute_query(self):
        """Test executing query"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = [{'id': 1, 'name': 'test'}]
        
        with patch.object(self.db_manager, 'get_connection', return_value=mock_conn):
            results = self.db_manager.execute_query("SELECT * FROM users")
            
            mock_cursor.execute.assert_called_with("SELECT * FROM users", ())
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0]['name'], 'test')

if __name__ == '__main__':
    unittest.main()
