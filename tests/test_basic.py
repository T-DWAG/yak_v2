#!/usr/bin/env python3
"""
Basic tests for the yak similarity analyzer
"""

import sys
import os
import unittest

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

class TestBasicImports(unittest.TestCase):
    """Test that core modules can be imported"""
    
    def test_dual_key_system_import(self):
        """Test dual key system import"""
        try:
            from dual_key_system import DualKeySystem
            system = DualKeySystem()
            self.assertIsNotNone(system)
        except ImportError as e:
            self.fail(f"Failed to import DualKeySystem: {e}")
    
    def test_license_manager_import(self):
        """Test license manager import"""
        try:
            from license_manager_simple import LicenseManager
            manager = LicenseManager()
            self.assertIsNotNone(manager)
        except ImportError as e:
            self.fail(f"Failed to import LicenseManager: {e}")

class TestDualKeySystem(unittest.TestCase):
    """Test dual key system functionality"""
    
    def setUp(self):
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
        from dual_key_system import DualKeySystem
        self.dual_key = DualKeySystem()
    
    def test_provider_key_generation(self):
        """Test provider key generation"""
        import json
        client_data = {
            "client_id": "test_client",
            "images_used": 100,
            "total_sessions": 5,
            "last_session_date": "2025-08-22"
        }
        
        auth_params = {
            "total_images_allowed": 5000,
            "valid_until": "2025-09-22T13:30:00",
            "allowed_ips": ["127.0.0.1"]
        }
        
        success, provider_key = self.dual_key.generate_provider_key(json.dumps(client_data), auth_params)
        self.assertTrue(success)
        self.assertIsInstance(provider_key, str)
        self.assertIn("license_id", provider_key)

if __name__ == '__main__':
    unittest.main()