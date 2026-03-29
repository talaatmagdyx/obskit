"""Tests to cover double-check locking inner branches."""

from __future__ import annotations


class _FakeDict(dict):
    """A dict that lies about __contains__ on the first call for a specific key."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._first_call_done = False
        self._target_key = None

    def __contains__(self, key):
        if key == self._target_key and not self._first_call_done:
            self._first_call_done = True
            return False  # Lie: pretend the key doesn't exist
        return super().__contains__(key)


class TestDoubleCheckLockingBranches:
    """Cover the inner branch of double-check locking patterns.

    The inner branch (e.g. line 394->397 in adaptive_sampling) is the path where:
    - Outer check: name NOT in dict (True - we enter the lock block)
    - Inner check: name IS in dict (False - someone else added it during lock wait)
    This simulates the double-check locking race condition.
    """

    def test_adaptive_sampler_inner_lock_already_exists(self):
        """Line 394->397: inner check finds sampler already exists."""
        import obskit.adaptive_sampling as module

        unique_name = "__inner_lock_test_sampler__"
        module._samplers.pop(unique_name, None)

        # Create and pre-populate with the sampler
        from obskit.adaptive_sampling import AdaptiveSampler

        existing_sampler = AdaptiveSampler(name=unique_name)

        # Create a custom dict that lies on the first outer check
        fake_dict = _FakeDict()
        fake_dict._target_key = unique_name
        fake_dict[unique_name] = existing_sampler  # already exists

        original_dict = module._samplers
        module._samplers = fake_dict
        try:
            result = module.get_adaptive_sampler(unique_name)
            # The outer check returned False (lie), we entered the lock,
            # inner check found the sampler, so we returned existing one
            assert result is existing_sampler
        finally:
            module._samplers = original_dict
            module._samplers.pop(unique_name, None)

    def test_audit_trail_inner_lock_already_exists(self):
        """Line 425->428: inner check finds audit trail already exists."""
        import obskit.audit as module

        unique_name = "__inner_lock_test_trail__"
        module._trails.pop(unique_name, None)

        from obskit.audit import AuditTrail

        existing_trail = AuditTrail(unique_name)

        fake_dict = _FakeDict()
        fake_dict._target_key = unique_name
        fake_dict[unique_name] = existing_trail

        original_dict = module._trails
        module._trails = fake_dict
        try:
            result = module.get_audit_trail(unique_name)
            assert result is existing_trail
        finally:
            module._trails = original_dict
            module._trails.pop(unique_name, None)

    def test_executor_tracker_inner_lock_already_exists(self):
        """Line 412->415: inner check finds executor tracker already exists."""
        import obskit.executor as module

        unique_name = "__inner_lock_test_tracker__"
        module._trackers.pop(unique_name, None)

        from obskit.executor import ExecutorTracker

        existing_tracker = ExecutorTracker(unique_name)

        fake_dict = _FakeDict()
        fake_dict._target_key = unique_name
        fake_dict[unique_name] = existing_tracker

        original_dict = module._trackers
        module._trackers = fake_dict
        try:
            result = module.get_executor_tracker(unique_name)
            assert result is existing_tracker
        finally:
            module._trackers = original_dict
            module._trackers.pop(unique_name, None)
