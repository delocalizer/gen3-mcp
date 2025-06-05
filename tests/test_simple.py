"""Simple tests (verify pytest working)"""

from unittest import TestCase


class TestPackage(TestCase):

    def test_imports(self):
        """Test that all main imports work"""
        try:
            from gen3_mcp import (
                Config,
                Gen3Client,
                Gen3MCPError,
                QueryService,
                SchemaManager,
            )
        except ImportError as e:
            self.fail(e)
