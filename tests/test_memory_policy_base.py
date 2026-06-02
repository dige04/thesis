"""Unit tests for MemoryPolicy abstract base class.

Tests verify:
1. MemoryPolicy is abstract and cannot be instantiated directly
2. Subclasses must implement all three abstract methods
3. The interface enforces correct method signatures
4. Policy name attribute is accessible
"""

import pytest

from src.memory.policies.base import MemoryPolicy


class TestMemoryPolicyInterface:
    """Test the MemoryPolicy abstract interface."""

    def test_cannot_instantiate_abstract_class(self):
        """Verify MemoryPolicy cannot be instantiated directly."""
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            MemoryPolicy()

    def test_subclass_must_implement_retrieve(self):
        """Verify subclass must implement retrieve() method."""
        class IncompletePolicy(MemoryPolicy):
            name = "incomplete"

            def write(self, memory_store, record):
                pass

            def maintain(self, memory_store):
                pass

        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            IncompletePolicy()

    def test_subclass_must_implement_write(self):
        """Verify subclass must implement write() method."""
        class IncompletePolicy(MemoryPolicy):
            name = "incomplete"

            def retrieve(self, task, memory_store, top_k, token_budget):
                return []

            def maintain(self, memory_store):
                pass

        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            IncompletePolicy()

    def test_subclass_must_implement_maintain(self):
        """Verify subclass must implement maintain() method."""
        class IncompletePolicy(MemoryPolicy):
            name = "incomplete"

            def retrieve(self, task, memory_store, top_k, token_budget):
                return []

            def write(self, memory_store, record):
                pass

        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            IncompletePolicy()

    def test_complete_subclass_can_be_instantiated(self):
        """Verify complete subclass implementing all methods can be instantiated."""
        class CompletePolicy(MemoryPolicy):
            name = "complete"

            def retrieve(self, task, memory_store, top_k, token_budget):
                return []

            def write(self, memory_store, record):
                pass

            def maintain(self, memory_store):
                pass

        # Should not raise
        policy = CompletePolicy()
        assert policy.name == "complete"

    def test_policy_name_attribute_accessible(self):
        """Verify policy name attribute is accessible."""
        class TestPolicy(MemoryPolicy):
            name = "test_policy"

            def retrieve(self, task, memory_store, top_k, token_budget):
                return []

            def write(self, memory_store, record):
                pass

            def maintain(self, memory_store):
                pass

        policy = TestPolicy()
        assert hasattr(policy, "name")
        assert policy.name == "test_policy"

    def test_retrieve_method_signature(self):
        """Verify retrieve() has correct method signature."""
        class TestPolicy(MemoryPolicy):
            name = "test"

            def retrieve(self, task, memory_store, top_k, token_budget):
                # Verify parameters are accessible
                assert task is not None
                assert memory_store is not None
                assert isinstance(top_k, int)
                assert isinstance(token_budget, int)
                return []

            def write(self, memory_store, record):
                pass

            def maintain(self, memory_store):
                pass

        policy = TestPolicy()

        # Mock objects for testing
        class MockTask:
            pass

        class MockStore:
            pass

        result = policy.retrieve(MockTask(), MockStore(), 5, 2000)
        assert isinstance(result, list)

    def test_write_method_signature(self):
        """Verify write() has correct method signature."""
        class TestPolicy(MemoryPolicy):
            name = "test"

            def retrieve(self, task, memory_store, top_k, token_budget):
                return []

            def write(self, memory_store, record):
                # Verify parameters are accessible
                assert memory_store is not None
                assert record is not None

            def maintain(self, memory_store):
                pass

        policy = TestPolicy()

        # Mock objects for testing
        class MockStore:
            pass

        class MockRecord:
            pass

        # Should not raise
        policy.write(MockStore(), MockRecord())

    def test_maintain_method_signature(self):
        """Verify maintain() has correct method signature."""
        class TestPolicy(MemoryPolicy):
            name = "test"

            def retrieve(self, task, memory_store, top_k, token_budget):
                return []

            def write(self, memory_store, record):
                pass

            def maintain(self, memory_store):
                # Verify parameter is accessible
                assert memory_store is not None

        policy = TestPolicy()

        # Mock object for testing
        class MockStore:
            pass

        # Should not raise
        policy.maintain(MockStore())


class TestMemoryPolicyDocumentation:
    """Test that MemoryPolicy has proper documentation."""

    def test_class_has_docstring(self):
        """Verify MemoryPolicy class has docstring."""
        assert MemoryPolicy.__doc__ is not None
        assert len(MemoryPolicy.__doc__) > 0

    def test_retrieve_has_docstring(self):
        """Verify retrieve() method has docstring."""
        assert MemoryPolicy.retrieve.__doc__ is not None
        assert "shared_retrieve" in MemoryPolicy.retrieve.__doc__
        assert "CRITICAL" in MemoryPolicy.retrieve.__doc__

    def test_write_has_docstring(self):
        """Verify write() method has docstring."""
        assert MemoryPolicy.write.__doc__ is not None
        assert len(MemoryPolicy.write.__doc__) > 0

    def test_maintain_has_docstring(self):
        """Verify maintain() method has docstring."""
        assert MemoryPolicy.maintain.__doc__ is not None
        assert len(MemoryPolicy.maintain.__doc__) > 0

    def test_docstring_mentions_no_memory_exception(self):
        """Verify retrieve() docstring mentions No Memory policy exception."""
        assert "No Memory" in MemoryPolicy.retrieve.__doc__
        assert "except" in MemoryPolicy.retrieve.__doc__.lower()
