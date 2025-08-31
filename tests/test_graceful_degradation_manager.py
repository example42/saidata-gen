"""
Tests for GracefulDegradationManager.

This module contains tests for the graceful degradation functionality
that handles provider failures and provides fallback options.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

from saidata_gen.core.graceful_degradation import (
    GracefulDegradationManager, ProviderFailure, DegradationEvent
)


class TestGracefulDegradationManager:
    """Test cases for GracefulDegradationManager."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.manager = GracefulDegradationManager(
            failure_threshold=3,
            recovery_timeout=300,  # 5 minutes
            permanent_failure_timeout=3600  # 1 hour
        )
    
    def test_initialization(self):
        """Test GracefulDegradationManager initialization."""
        manager = GracefulDegradationManager(
            failure_threshold=5,
            recovery_timeout=600,
            permanent_failure_timeout=7200
        )
        
        assert manager.failure_threshold == 5
        assert manager.recovery_timeout == 600
        assert manager.permanent_failure_timeout == 7200
        assert len(manager._provider_failures) == 0
        assert len(manager._unavailable_providers) == 0
        assert len(manager._permanently_failed_providers) == 0
        assert len(manager._degradation_events) == 0
        assert len(manager._alternative_sources) == 0
        assert len(manager._recovery_attempts) == 0
        assert manager._stats['total_failures'] == 0
    
    def test_mark_provider_unavailable_single_failure(self):
        """Test marking a provider unavailable with single failure (below threshold)."""
        self.manager.mark_provider_unavailable(
            provider="test_provider",
            reason="Network timeout",
            url="https://example.com",
            error_type="network"
        )
        
        # Should not be marked as unavailable yet (below threshold)
        assert "test_provider" not in self.manager._unavailable_providers
        assert len(self.manager._provider_failures["test_provider"]) == 1
        assert self.manager._stats['total_failures'] == 1
        assert self.manager._stats['providers_marked_unavailable'] == 0
    
    def test_mark_provider_unavailable_threshold_reached(self):
        """Test marking a provider unavailable when threshold is reached."""
        # Add failures up to threshold
        for i in range(3):
            self.manager.mark_provider_unavailable(
                provider="test_provider",
                reason=f"Network timeout {i+1}",
                error_type="network"
            )
        
        # Should now be marked as unavailable
        assert "test_provider" in self.manager._unavailable_providers
        assert len(self.manager._provider_failures["test_provider"]) == 3
        assert self.manager._stats['total_failures'] == 3
        assert self.manager._stats['providers_marked_unavailable'] == 1
        assert len(self.manager._degradation_events) >= 1
    
    def test_mark_provider_unavailable_permanent_failure(self):
        """Test marking a provider as permanently unavailable."""
        self.manager.mark_provider_unavailable(
            provider="test_provider",
            reason="Missing system dependency",
            error_type="dependency",
            permanent=True
        )
        
        # Should be marked as both unavailable and permanently failed
        assert "test_provider" in self.manager._unavailable_providers
        assert "test_provider" in self.manager._permanently_failed_providers
        assert self.manager._stats['total_failures'] == 1
        assert self.manager._stats['providers_marked_unavailable'] == 1
    
    def test_get_alternative_sources_no_alternatives(self):
        """Test getting alternative sources when none are registered."""
        alternatives = self.manager.get_alternative_sources("test_provider")
        
        assert alternatives == []
        assert self.manager._stats['fallbacks_used'] == 0
    
    def test_get_alternative_sources_with_alternatives(self):
        """Test getting alternative sources when alternatives are registered."""
        # Register alternatives
        self.manager.register_alternative_sources(
            "test_provider", 
            ["alt_provider1", "alt_provider2"]
        )
        
        # Mark provider as unavailable
        for i in range(3):
            self.manager.mark_provider_unavailable(
                provider="test_provider",
                reason=f"Failure {i+1}"
            )
        
        alternatives = self.manager.get_alternative_sources("test_provider")
        
        assert alternatives == ["alt_provider1", "alt_provider2"]
        assert self.manager._stats['fallbacks_used'] == 1
        assert len(self.manager._degradation_events) >= 2  # unavailable + fallback events
    
    def test_get_alternative_sources_filters_unavailable_alternatives(self):
        """Test that unavailable alternatives are filtered out."""
        # Register alternatives
        self.manager.register_alternative_sources(
            "test_provider", 
            ["alt_provider1", "alt_provider2", "alt_provider3"]
        )
        
        # Mark main provider and one alternative as unavailable
        for i in range(3):
            self.manager.mark_provider_unavailable(
                provider="test_provider",
                reason=f"Failure {i+1}"
            )
            self.manager.mark_provider_unavailable(
                provider="alt_provider2",
                reason=f"Alt failure {i+1}"
            )
        
        alternatives = self.manager.get_alternative_sources("test_provider")
        
        # Should only return available alternatives
        assert alternatives == ["alt_provider1", "alt_provider3"]
        assert "alt_provider2" not in alternatives
    
    def test_log_degradation_event(self):
        """Test logging degradation events."""
        additional_info = {"error_count": 3, "url": "https://example.com"}
        
        self.manager.log_degradation_event(
            provider="test_provider",
            event_type="marked_unavailable",
            reason="Threshold reached",
            additional_info=additional_info
        )
        
        assert len(self.manager._degradation_events) == 1
        event = self.manager._degradation_events[0]
        assert event.provider == "test_provider"
        assert event.event_type == "marked_unavailable"
        assert event.reason == "Threshold reached"
        assert event.additional_info == additional_info
        assert isinstance(event.timestamp, datetime)
    
    def test_log_degradation_event_limits_history(self):
        """Test that degradation event history is limited."""
        # Add more than 1000 events
        for i in range(1050):
            self.manager.log_degradation_event(
                provider=f"provider_{i % 10}",
                event_type="test_event",
                reason=f"Test reason {i}"
            )
        
        # Should be limited to 1000 events
        assert len(self.manager._degradation_events) == 1000
        # Should keep the most recent events
        assert self.manager._degradation_events[-1].reason == "Test reason 1049"
    
    def test_register_alternative_sources(self):
        """Test registering alternative sources."""
        alternatives = ["alt1", "alt2", "alt3"]
        
        self.manager.register_alternative_sources("test_provider", alternatives)
        
        assert self.manager._alternative_sources["test_provider"] == alternatives
    
    def test_is_provider_available_available_provider(self):
        """Test checking availability of an available provider."""
        assert self.manager.is_provider_available("test_provider") is True
    
    def test_is_provider_available_unavailable_provider(self):
        """Test checking availability of an unavailable provider."""
        # Mark provider as unavailable
        for i in range(3):
            self.manager.mark_provider_unavailable(
                provider="test_provider",
                reason=f"Failure {i+1}"
            )
        
        assert self.manager.is_provider_available("test_provider") is False
    
    def test_is_provider_available_permanently_failed_provider(self):
        """Test checking availability of a permanently failed provider."""
        self.manager.mark_provider_unavailable(
            provider="test_provider",
            reason="Permanent failure",
            permanent=True
        )
        
        assert self.manager.is_provider_available("test_provider") is False
    
    def test_attempt_provider_recovery_available_provider(self):
        """Test attempting recovery of an available provider."""
        result = self.manager.attempt_provider_recovery("test_provider")
        
        assert result is True
    
    def test_attempt_provider_recovery_permanently_failed_provider(self):
        """Test attempting recovery of a permanently failed provider."""
        self.manager.mark_provider_unavailable(
            provider="test_provider",
            reason="Permanent failure",
            permanent=True
        )
        
        result = self.manager.attempt_provider_recovery("test_provider")
        
        assert result is False
    
    def test_attempt_provider_recovery_timeout_not_reached(self):
        """Test attempting recovery when timeout hasn't been reached."""
        # Mark provider as unavailable
        for i in range(3):
            self.manager.mark_provider_unavailable(
                provider="test_provider",
                reason=f"Failure {i+1}"
            )
        
        # Attempt recovery immediately (should succeed first time)
        result1 = self.manager.attempt_provider_recovery("test_provider")
        assert result1 is True
        
        # Attempt recovery again immediately (should fail due to timeout)
        result2 = self.manager.attempt_provider_recovery("test_provider")
        assert result2 is False
    
    @patch('saidata_gen.core.graceful_degradation.datetime')
    def test_attempt_provider_recovery_timeout_reached(self, mock_datetime):
        """Test attempting recovery when timeout has been reached."""
        # Set up mock datetime
        base_time = datetime(2023, 1, 1, 12, 0, 0)
        mock_datetime.now.return_value = base_time
        
        # Mark provider as unavailable
        for i in range(3):
            self.manager.mark_provider_unavailable(
                provider="test_provider",
                reason=f"Failure {i+1}"
            )
        
        # First recovery attempt
        result1 = self.manager.attempt_provider_recovery("test_provider")
        assert result1 is True
        
        # Advance time beyond recovery timeout
        mock_datetime.now.return_value = base_time + timedelta(seconds=400)
        
        # Second recovery attempt should succeed
        result2 = self.manager.attempt_provider_recovery("test_provider")
        assert result2 is True
    
    def test_mark_provider_recovered(self):
        """Test marking a provider as recovered."""
        # Mark provider as unavailable
        for i in range(3):
            self.manager.mark_provider_unavailable(
                provider="test_provider",
                reason=f"Failure {i+1}"
            )
        
        assert "test_provider" in self.manager._unavailable_providers
        
        # Mark as recovered
        self.manager.mark_provider_recovered("test_provider")
        
        assert "test_provider" not in self.manager._unavailable_providers
        assert self.manager._stats['recoveries'] == 1
        
        # Should have logged a recovery event
        recovery_events = [
            e for e in self.manager._degradation_events 
            if e.event_type == 'recovered'
        ]
        assert len(recovery_events) == 1
    
    def test_mark_provider_recovered_not_unavailable(self):
        """Test marking a provider as recovered when it wasn't unavailable."""
        # Mark as recovered without being unavailable first
        self.manager.mark_provider_recovered("test_provider")
        
        # Should not affect stats
        assert self.manager._stats['recoveries'] == 0
    
    def test_get_provider_status_available_provider(self):
        """Test getting status of an available provider."""
        status = self.manager.get_provider_status("test_provider")
        
        assert status['provider'] == "test_provider"
        assert status['available'] is True
        assert status['unavailable'] is False
        assert status['permanently_failed'] is False
        assert status['total_failures'] == 0
        assert status['recent_failures'] == 0
        assert status['failure_threshold'] == 3
        assert status['alternatives'] == []
        assert status['last_failure'] is None
        assert status['next_recovery_attempt'] is None
    
    def test_get_provider_status_unavailable_provider(self):
        """Test getting status of an unavailable provider."""
        # Register alternatives
        self.manager.register_alternative_sources(
            "test_provider", 
            ["alt1", "alt2"]
        )
        
        # Mark provider as unavailable
        for i in range(3):
            self.manager.mark_provider_unavailable(
                provider="test_provider",
                reason=f"Network failure {i+1}",
                url="https://example.com",
                error_type="network"
            )
        
        status = self.manager.get_provider_status("test_provider")
        
        assert status['provider'] == "test_provider"
        assert status['available'] is False
        assert status['unavailable'] is True
        assert status['permanently_failed'] is False
        assert status['total_failures'] == 3
        assert status['recent_failures'] == 3
        assert status['alternatives'] == ["alt1", "alt2"]
        assert status['last_failure'] is not None
        assert status['last_failure']['reason'] == "Network failure 3"
        assert status['last_failure']['error_type'] == "network"
        assert status['last_failure']['url'] == "https://example.com"
    
    def test_get_degradation_summary(self):
        """Test getting degradation summary."""
        # Create some failures and events
        self.manager.mark_provider_unavailable(
            "provider1", "Failure 1", permanent=True
        )
        
        for i in range(3):
            self.manager.mark_provider_unavailable(
                "provider2", f"Failure {i+1}"
            )
        
        summary = self.manager.get_degradation_summary()
        
        assert "provider1" in summary['permanently_failed_providers']
        assert "provider2" in summary['unavailable_providers']
        assert summary['total_providers_with_failures'] == 2
        assert summary['statistics']['total_failures'] == 4
        assert summary['statistics']['providers_marked_unavailable'] == 2
        assert len(summary['recent_events']) <= 10
    
    def test_get_degradation_events_no_filters(self):
        """Test getting degradation events without filters."""
        # Create some events
        for i in range(5):
            self.manager.log_degradation_event(
                provider=f"provider_{i % 2}",
                event_type="test_event",
                reason=f"Test reason {i}"
            )
        
        events = self.manager.get_degradation_events()
        
        assert len(events) == 5
        # Should be sorted by timestamp (most recent first)
        assert events[0]['reason'] == "Test reason 4"
        assert events[-1]['reason'] == "Test reason 0"
    
    def test_get_degradation_events_with_provider_filter(self):
        """Test getting degradation events filtered by provider."""
        # Create events for different providers
        for i in range(6):
            self.manager.log_degradation_event(
                provider=f"provider_{i % 3}",
                event_type="test_event",
                reason=f"Test reason {i}"
            )
        
        events = self.manager.get_degradation_events(provider="provider_1")
        
        assert len(events) == 2
        assert all(event['provider'] == "provider_1" for event in events)
    
    def test_get_degradation_events_with_event_type_filter(self):
        """Test getting degradation events filtered by event type."""
        # Create events with different types
        event_types = ["marked_unavailable", "fallback_used", "recovered"]
        for i in range(6):
            self.manager.log_degradation_event(
                provider="test_provider",
                event_type=event_types[i % 3],
                reason=f"Test reason {i}"
            )
        
        events = self.manager.get_degradation_events(event_type="fallback_used")
        
        assert len(events) == 2
        assert all(event['event_type'] == "fallback_used" for event in events)
    
    def test_get_degradation_events_with_limit(self):
        """Test getting degradation events with limit."""
        # Create more events than the limit
        for i in range(10):
            self.manager.log_degradation_event(
                provider="test_provider",
                event_type="test_event",
                reason=f"Test reason {i}"
            )
        
        events = self.manager.get_degradation_events(limit=3)
        
        assert len(events) == 3
        # Should get the most recent events
        assert events[0]['reason'] == "Test reason 9"
        assert events[2]['reason'] == "Test reason 7"
    
    def test_cleanup_old_failures(self):
        """Test cleaning up old failure records."""
        # Create some old and new failures
        old_time = datetime.now() - timedelta(hours=25)  # Older than 24 hours
        new_time = datetime.now() - timedelta(hours=1)   # Within 24 hours
        
        # Add failures with different timestamps
        with patch('saidata_gen.core.graceful_degradation.datetime') as mock_datetime:
            # Old failure
            mock_datetime.now.return_value = old_time
            self.manager.mark_provider_unavailable(
                "provider1", "Old failure"
            )
            
            # New failure
            mock_datetime.now.return_value = new_time
            self.manager.mark_provider_unavailable(
                "provider1", "New failure"
            )
            self.manager.mark_provider_unavailable(
                "provider2", "Another new failure"
            )
            
            # Old event
            mock_datetime.now.return_value = old_time
            self.manager.log_degradation_event(
                "provider1", "old_event", "Old event"
            )
            
            # New event
            mock_datetime.now.return_value = new_time
            self.manager.log_degradation_event(
                "provider1", "new_event", "New event"
            )
        
        # Clean up old records
        removed_count = self.manager.cleanup_old_failures(max_age_hours=24)
        
        assert removed_count >= 1  # At least old failure or old event
        
        # Check that new records are kept
        assert len(self.manager._provider_failures["provider1"]) == 1
        assert self.manager._provider_failures["provider1"][0].reason == "New failure"
        assert len(self.manager._provider_failures["provider2"]) == 1
        
        # Check that new events are kept
        new_events = [e for e in self.manager._degradation_events if e.reason == "New event"]
        assert len(new_events) == 1
    
    def test_reset_provider_failures(self):
        """Test resetting failures for a specific provider."""
        # Create failures for multiple providers
        for i in range(3):
            self.manager.mark_provider_unavailable(
                "provider1", f"Failure {i+1}"
            )
            self.manager.mark_provider_unavailable(
                "provider2", f"Failure {i+1}"
            )
        
        # Attempt recovery for provider1 to add to recovery attempts
        self.manager.attempt_provider_recovery("provider1")
        
        assert "provider1" in self.manager._unavailable_providers
        assert "provider2" in self.manager._unavailable_providers
        assert "provider1" in self.manager._provider_failures
        assert "provider2" in self.manager._provider_failures
        
        # Reset provider1
        self.manager.reset_provider_failures("provider1")
        
        # Provider1 should be reset, provider2 should remain
        assert "provider1" not in self.manager._unavailable_providers
        assert "provider2" in self.manager._unavailable_providers
        assert "provider1" not in self.manager._provider_failures
        assert "provider2" in self.manager._provider_failures
        assert "provider1" not in self.manager._recovery_attempts
    
    def test_reset_all_failures(self):
        """Test resetting all failure tracking."""
        # Create failures and events
        for i in range(3):
            self.manager.mark_provider_unavailable(
                "provider1", f"Failure {i+1}"
            )
        
        self.manager.log_degradation_event(
            "provider1", "test_event", "Test event"
        )
        
        # Verify data exists
        assert len(self.manager._provider_failures) > 0
        assert len(self.manager._unavailable_providers) > 0
        assert len(self.manager._degradation_events) > 0
        assert self.manager._stats['total_failures'] > 0
        
        # Reset all
        self.manager.reset_all_failures()
        
        # Verify everything is reset
        assert len(self.manager._provider_failures) == 0
        assert len(self.manager._unavailable_providers) == 0
        assert len(self.manager._permanently_failed_providers) == 0
        assert len(self.manager._recovery_attempts) == 0
        assert len(self.manager._degradation_events) == 0
        assert self.manager._stats['total_failures'] == 0
        assert self.manager._stats['providers_marked_unavailable'] == 0
        assert self.manager._stats['fallbacks_used'] == 0
        assert self.manager._stats['recoveries'] == 0
    
    def test_get_recent_failures_within_window(self):
        """Test getting recent failures within time window."""
        current_time = datetime.now()
        
        # Create failures at different times
        with patch('saidata_gen.core.graceful_degradation.datetime') as mock_datetime:
            # Old failure (outside window)
            mock_datetime.now.return_value = current_time - timedelta(hours=2)
            self.manager.mark_provider_unavailable(
                "test_provider", "Old failure"
            )
            
            # Recent failure (within window)
            mock_datetime.now.return_value = current_time - timedelta(minutes=30)
            self.manager.mark_provider_unavailable(
                "test_provider", "Recent failure"
            )
        
        # Get recent failures (default 60 minute window)
        recent_failures = self.manager._get_recent_failures("test_provider")
        
        assert len(recent_failures) == 1
        assert recent_failures[0].reason == "Recent failure"
    
    def test_should_attempt_recovery_no_previous_attempt(self):
        """Test recovery attempt when no previous attempt exists."""
        result = self.manager._should_attempt_recovery("test_provider")
        assert result is True
    
    def test_should_attempt_recovery_timeout_not_reached(self):
        """Test recovery attempt when timeout hasn't been reached."""
        # Record a recovery attempt
        self.manager._recovery_attempts["test_provider"] = datetime.now()
        
        result = self.manager._should_attempt_recovery("test_provider")
        assert result is False
    
    @patch('saidata_gen.core.graceful_degradation.datetime')
    def test_should_attempt_recovery_timeout_reached(self, mock_datetime):
        """Test recovery attempt when timeout has been reached."""
        base_time = datetime(2023, 1, 1, 12, 0, 0)
        
        # Record a recovery attempt in the past
        self.manager._recovery_attempts["test_provider"] = base_time
        
        # Set current time beyond recovery timeout
        mock_datetime.now.return_value = base_time + timedelta(seconds=400)
        
        result = self.manager._should_attempt_recovery("test_provider")
        assert result is True


class TestProviderFailure:
    """Test cases for ProviderFailure dataclass."""
    
    def test_provider_failure_creation(self):
        """Test ProviderFailure creation."""
        timestamp = datetime.now()
        failure = ProviderFailure(
            provider="test_provider",
            reason="Network timeout",
            timestamp=timestamp,
            url="https://example.com",
            error_type="network",
            retry_count=2,
            permanent=True
        )
        
        assert failure.provider == "test_provider"
        assert failure.reason == "Network timeout"
        assert failure.timestamp == timestamp
        assert failure.url == "https://example.com"
        assert failure.error_type == "network"
        assert failure.retry_count == 2
        assert failure.permanent is True
    
    def test_provider_failure_defaults(self):
        """Test ProviderFailure with default values."""
        failure = ProviderFailure(
            provider="test_provider",
            reason="Test failure",
            timestamp=datetime.now()
        )
        
        assert failure.url is None
        assert failure.error_type == "unknown"
        assert failure.retry_count == 0
        assert failure.permanent is False


class TestDegradationEvent:
    """Test cases for DegradationEvent dataclass."""
    
    def test_degradation_event_creation(self):
        """Test DegradationEvent creation."""
        timestamp = datetime.now()
        additional_info = {"error_count": 3}
        
        event = DegradationEvent(
            provider="test_provider",
            event_type="marked_unavailable",
            reason="Threshold reached",
            timestamp=timestamp,
            additional_info=additional_info
        )
        
        assert event.provider == "test_provider"
        assert event.event_type == "marked_unavailable"
        assert event.reason == "Threshold reached"
        assert event.timestamp == timestamp
        assert event.additional_info == additional_info
    
    def test_degradation_event_defaults(self):
        """Test DegradationEvent with default values."""
        event = DegradationEvent(
            provider="test_provider",
            event_type="test_event",
            reason="Test reason"
        )
        
        assert isinstance(event.timestamp, datetime)
        assert event.additional_info == {}


# Integration tests
class TestGracefulDegradationManagerIntegration:
    """Integration tests for GracefulDegradationManager."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.manager = GracefulDegradationManager(
            failure_threshold=2,
            recovery_timeout=60,
            permanent_failure_timeout=300
        )
    
    def test_complete_failure_and_recovery_workflow(self):
        """Test complete failure and recovery workflow."""
        # Register alternatives
        self.manager.register_alternative_sources(
            "primary_provider",
            ["backup_provider1", "backup_provider2"]
        )
        
        # Provider is initially available
        assert self.manager.is_provider_available("primary_provider") is True
        
        # Add failures to reach threshold
        self.manager.mark_provider_unavailable(
            "primary_provider", "Network error 1", error_type="network"
        )
        assert self.manager.is_provider_available("primary_provider") is True  # Still available
        
        self.manager.mark_provider_unavailable(
            "primary_provider", "Network error 2", error_type="network"
        )
        assert self.manager.is_provider_available("primary_provider") is False  # Now unavailable
        
        # Get alternatives
        alternatives = self.manager.get_alternative_sources("primary_provider")
        assert alternatives == ["backup_provider1", "backup_provider2"]
        
        # Attempt recovery
        can_recover = self.manager.attempt_provider_recovery("primary_provider")
        assert can_recover is True
        
        # Mark as recovered
        self.manager.mark_provider_recovered("primary_provider")
        assert self.manager.is_provider_available("primary_provider") is True
        
        # Check statistics
        summary = self.manager.get_degradation_summary()
        assert summary['statistics']['total_failures'] == 2
        assert summary['statistics']['providers_marked_unavailable'] == 1
        assert summary['statistics']['fallbacks_used'] == 1
        assert summary['statistics']['recoveries'] == 1
    
    def test_permanent_failure_workflow(self):
        """Test permanent failure workflow."""
        # Mark provider as permanently failed
        self.manager.mark_provider_unavailable(
            "test_provider",
            "Missing system dependency",
            error_type="dependency",
            permanent=True
        )
        
        # Should be unavailable and permanently failed
        assert self.manager.is_provider_available("test_provider") is False
        
        # Recovery should not be attempted
        can_recover = self.manager.attempt_provider_recovery("test_provider")
        assert can_recover is False
        
        # Check status
        status = self.manager.get_provider_status("test_provider")
        assert status['permanently_failed'] is True
        assert status['unavailable'] is True
    
    def test_multiple_providers_with_cascading_failures(self):
        """Test handling multiple providers with cascading failures."""
        # Set up provider hierarchy: primary -> backup1 -> backup2
        self.manager.register_alternative_sources("primary", ["backup1"])
        self.manager.register_alternative_sources("backup1", ["backup2"])
        
        # Fail primary provider
        for i in range(2):
            self.manager.mark_provider_unavailable(
                "primary", f"Primary failure {i+1}"
            )
        
        # Get alternatives for primary (should get backup1)
        alternatives = self.manager.get_alternative_sources("primary")
        assert alternatives == ["backup1"]
        
        # Fail backup1 provider
        for i in range(2):
            self.manager.mark_provider_unavailable(
                "backup1", f"Backup1 failure {i+1}"
            )
        
        # Now primary alternatives should be empty (backup1 is unavailable)
        alternatives = self.manager.get_alternative_sources("primary")
        assert alternatives == []
        
        # But backup1 should have backup2 as alternative
        alternatives = self.manager.get_alternative_sources("backup1")
        assert alternatives == ["backup2"]
        
        # Check overall status
        summary = self.manager.get_degradation_summary()
        assert len(summary['unavailable_providers']) == 2
        assert summary['statistics']['providers_marked_unavailable'] == 2
    
    @patch('saidata_gen.core.graceful_degradation.logger')
    def test_logging_integration(self, mock_logger):
        """Test that appropriate log messages are generated."""
        # Mark provider unavailable
        for i in range(2):
            self.manager.mark_provider_unavailable(
                "test_provider", f"Network failure {i+1}"
            )
        
        # Should have logged warnings and info messages
        assert mock_logger.warning.called
        assert mock_logger.info.called
        
        # Check that specific log messages were called
        warning_calls = [call[0][0] for call in mock_logger.warning.call_args_list]
        info_calls = [call[0][0] for call in mock_logger.info.call_args_list]
        
        # Should have logged the unavailable warning
        unavailable_logs = [log for log in warning_calls if "marked as unavailable" in log]
        assert len(unavailable_logs) == 1
        
        # Should have logged degradation events
        degradation_logs = [log for log in info_calls if "Degradation event" in log]
        assert len(degradation_logs) >= 1