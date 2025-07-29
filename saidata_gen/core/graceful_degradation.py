"""
Graceful degradation manager for handling provider failures.

This module provides the GracefulDegradationManager class for tracking provider
failures and providing fallback options when providers become unavailable.
"""

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set

from saidata_gen.core.exceptions import SaidataGenError


logger = logging.getLogger(__name__)


@dataclass
class ProviderFailure:
    """Information about a provider failure."""
    provider: str
    reason: str
    timestamp: datetime
    url: Optional[str] = None
    error_type: str = "unknown"
    retry_count: int = 0
    permanent: bool = False


@dataclass
class DegradationEvent:
    """Information about a degradation event."""
    provider: str
    event_type: str  # 'marked_unavailable', 'fallback_used', 'recovered'
    reason: str
    timestamp: datetime = field(default_factory=datetime.now)
    additional_info: Dict[str, Any] = field(default_factory=dict)


class GracefulDegradationManager:
    """
    Manager for handling provider failures gracefully.
    
    This class tracks provider failures, manages fallback options, and provides
    monitoring capabilities for degraded service scenarios.
    """
    
    def __init__(self, 
                 failure_threshold: int = 3,
                 recovery_timeout: int = 300,  # 5 minutes
                 permanent_failure_timeout: int = 3600):  # 1 hour
        """
        Initialize the graceful degradation manager.
        
        Args:
            failure_threshold: Number of failures before marking provider as unavailable.
            recovery_timeout: Time in seconds before attempting to recover a failed provider.
            permanent_failure_timeout: Time in seconds before considering a failure permanent.
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.permanent_failure_timeout = permanent_failure_timeout
        
        # Track provider failures
        self._provider_failures: Dict[str, List[ProviderFailure]] = {}
        self._unavailable_providers: Set[str] = set()
        self._permanently_failed_providers: Set[str] = set()
        
        # Track degradation events for monitoring
        self._degradation_events: List[DegradationEvent] = []
        
        # Alternative sources mapping
        self._alternative_sources: Dict[str, List[str]] = {}
        
        # Provider recovery tracking
        self._recovery_attempts: Dict[str, datetime] = {}
        
        # Statistics
        self._stats = {
            'total_failures': 0,
            'providers_marked_unavailable': 0,
            'fallbacks_used': 0,
            'recoveries': 0
        }
    
    def mark_provider_unavailable(self, provider: str, reason: str, 
                                url: Optional[str] = None,
                                error_type: str = "unknown",
                                permanent: bool = False) -> None:
        """
        Mark a provider as unavailable due to failure.
        
        Args:
            provider: Name of the provider that failed.
            reason: Reason for the failure.
            url: Optional URL that failed.
            error_type: Type of error (network, ssl, data, dependency).
            permanent: Whether this is a permanent failure.
        """
        current_time = datetime.now()
        
        # Create failure record
        failure = ProviderFailure(
            provider=provider,
            reason=reason,
            timestamp=current_time,
            url=url,
            error_type=error_type,
            permanent=permanent
        )
        
        # Add to failure history
        if provider not in self._provider_failures:
            self._provider_failures[provider] = []
        
        self._provider_failures[provider].append(failure)
        self._stats['total_failures'] += 1
        
        # Check if we should mark the provider as unavailable
        recent_failures = self._get_recent_failures(provider)
        
        if permanent or len(recent_failures) >= self.failure_threshold:
            if provider not in self._unavailable_providers:
                self._unavailable_providers.add(provider)
                self._stats['providers_marked_unavailable'] += 1
                
                if permanent:
                    self._permanently_failed_providers.add(provider)
                
                # Log degradation event
                self.log_degradation_event(
                    provider=provider,
                    event_type='marked_unavailable',
                    reason=f"Failure threshold reached: {reason}",
                    additional_info={
                        'failure_count': len(recent_failures),
                        'error_type': error_type,
                        'permanent': permanent,
                        'url': url
                    }
                )
                
                logger.warning(
                    f"Provider {provider} marked as unavailable after {len(recent_failures)} failures. "
                    f"Latest reason: {reason}"
                )
            else:
                # Update existing failure
                logger.debug(f"Additional failure for already unavailable provider {provider}: {reason}")
        else:
            logger.info(
                f"Provider {provider} failure recorded ({len(recent_failures)}/{self.failure_threshold}): {reason}"
            )
    
    def get_alternative_sources(self, provider: str) -> List[str]:
        """
        Get alternative sources for a failed provider.
        
        Args:
            provider: Name of the provider to get alternatives for.
            
        Returns:
            List of alternative provider names, or empty list if none available.
        """
        alternatives = self._alternative_sources.get(provider, [])
        
        # Filter out alternatives that are also unavailable
        available_alternatives = [
            alt for alt in alternatives 
            if alt not in self._unavailable_providers
        ]
        
        if available_alternatives and provider in self._unavailable_providers:
            self._stats['fallbacks_used'] += 1
            
            # Log fallback usage
            self.log_degradation_event(
                provider=provider,
                event_type='fallback_used',
                reason=f"Using alternatives: {', '.join(available_alternatives)}",
                additional_info={
                    'alternatives': available_alternatives,
                    'total_alternatives': len(alternatives)
                }
            )
            
            logger.info(
                f"Using alternative sources for {provider}: {', '.join(available_alternatives)}"
            )
        
        return available_alternatives
    
    def log_degradation_event(self, provider: str, event_type: str, reason: str,
                            additional_info: Optional[Dict[str, Any]] = None) -> None:
        """
        Log a degradation event for monitoring and debugging.
        
        Args:
            provider: Name of the provider.
            event_type: Type of event (marked_unavailable, fallback_used, recovered).
            reason: Reason for the event.
            additional_info: Optional additional information about the event.
        """
        event = DegradationEvent(
            provider=provider,
            event_type=event_type,
            reason=reason,
            additional_info=additional_info or {}
        )
        
        self._degradation_events.append(event)
        
        # Keep only recent events (last 1000 events)
        if len(self._degradation_events) > 1000:
            self._degradation_events = self._degradation_events[-1000:]
        
        logger.info(
            f"Degradation event for {provider}: {event_type} - {reason}"
        )
    
    def register_alternative_sources(self, provider: str, alternatives: List[str]) -> None:
        """
        Register alternative sources for a provider.
        
        Args:
            provider: Name of the primary provider.
            alternatives: List of alternative provider names.
        """
        self._alternative_sources[provider] = alternatives
        logger.debug(f"Registered {len(alternatives)} alternative sources for {provider}")
    
    def is_provider_available(self, provider: str) -> bool:
        """
        Check if a provider is currently available.
        
        Args:
            provider: Name of the provider to check.
            
        Returns:
            True if the provider is available, False otherwise.
        """
        if provider in self._permanently_failed_providers:
            return False
        
        if provider not in self._unavailable_providers:
            return True
        
        # Provider is marked as unavailable
        return False
    
    def attempt_provider_recovery(self, provider: str) -> bool:
        """
        Attempt to recover a failed provider.
        
        Args:
            provider: Name of the provider to recover.
            
        Returns:
            True if recovery should be attempted, False otherwise.
        """
        if provider in self._permanently_failed_providers:
            logger.debug(f"Provider {provider} is permanently failed, not attempting recovery")
            return False
        
        if provider not in self._unavailable_providers:
            logger.debug(f"Provider {provider} is not marked as unavailable")
            return True
        
        if not self._should_attempt_recovery(provider):
            logger.debug(f"Provider {provider} recovery timeout not reached")
            return False
        
        # Mark recovery attempt
        self._recovery_attempts[provider] = datetime.now()
        
        logger.info(f"Attempting recovery for provider {provider}")
        return True
    
    def mark_provider_recovered(self, provider: str) -> None:
        """
        Mark a provider as recovered from failure.
        
        Args:
            provider: Name of the provider that recovered.
        """
        if provider in self._unavailable_providers:
            self._unavailable_providers.remove(provider)
            self._stats['recoveries'] += 1
            
            # Log recovery event
            self.log_degradation_event(
                provider=provider,
                event_type='recovered',
                reason="Provider successfully recovered",
                additional_info={
                    'recovery_time': datetime.now().isoformat()
                }
            )
            
            logger.info(f"Provider {provider} has recovered and is now available")
        
        # Clear recovery attempt tracking
        if provider in self._recovery_attempts:
            del self._recovery_attempts[provider]
    
    def get_provider_status(self, provider: str) -> Dict[str, Any]:
        """
        Get detailed status information for a provider.
        
        Args:
            provider: Name of the provider.
            
        Returns:
            Dictionary containing provider status information.
        """
        failures = self._provider_failures.get(provider, [])
        recent_failures = self._get_recent_failures(provider)
        
        status = {
            'provider': provider,
            'available': self.is_provider_available(provider),
            'unavailable': provider in self._unavailable_providers,
            'permanently_failed': provider in self._permanently_failed_providers,
            'total_failures': len(failures),
            'recent_failures': len(recent_failures),
            'failure_threshold': self.failure_threshold,
            'alternatives': self._alternative_sources.get(provider, []),
            'last_failure': None,
            'next_recovery_attempt': None
        }
        
        if failures:
            status['last_failure'] = {
                'timestamp': failures[-1].timestamp.isoformat(),
                'reason': failures[-1].reason,
                'error_type': failures[-1].error_type,
                'url': failures[-1].url
            }
        
        if provider in self._recovery_attempts:
            next_attempt = self._recovery_attempts[provider] + timedelta(seconds=self.recovery_timeout)
            status['next_recovery_attempt'] = next_attempt.isoformat()
        
        return status
    
    def get_degradation_summary(self) -> Dict[str, Any]:
        """
        Get a summary of the current degradation state.
        
        Returns:
            Dictionary containing degradation summary.
        """
        return {
            'unavailable_providers': list(self._unavailable_providers),
            'permanently_failed_providers': list(self._permanently_failed_providers),
            'total_providers_with_failures': len(self._provider_failures),
            'statistics': self._stats.copy(),
            'recent_events': [
                {
                    'provider': event.provider,
                    'event_type': event.event_type,
                    'reason': event.reason,
                    'timestamp': event.timestamp.isoformat()
                }
                for event in self._degradation_events[-10:]  # Last 10 events
            ]
        }
    
    def get_degradation_events(self, provider: Optional[str] = None, 
                             event_type: Optional[str] = None,
                             limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get degradation events with optional filtering.
        
        Args:
            provider: Optional provider name to filter by.
            event_type: Optional event type to filter by.
            limit: Maximum number of events to return.
            
        Returns:
            List of degradation events.
        """
        events = self._degradation_events
        
        # Apply filters
        if provider:
            events = [e for e in events if e.provider == provider]
        
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        
        # Sort by timestamp (most recent first) and limit
        events = sorted(events, key=lambda e: e.timestamp, reverse=True)[:limit]
        
        return [
            {
                'provider': event.provider,
                'event_type': event.event_type,
                'reason': event.reason,
                'timestamp': event.timestamp.isoformat(),
                'additional_info': event.additional_info
            }
            for event in events
        ]
    
    def cleanup_old_failures(self, max_age_hours: int = 24) -> int:
        """
        Clean up old failure records to prevent memory growth.
        
        Args:
            max_age_hours: Maximum age of failure records to keep in hours.
            
        Returns:
            Number of failure records removed.
        """
        cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
        removed_count = 0
        
        for provider in list(self._provider_failures.keys()):
            original_count = len(self._provider_failures[provider])
            self._provider_failures[provider] = [
                f for f in self._provider_failures[provider]
                if f.timestamp > cutoff_time
            ]
            removed_count += original_count - len(self._provider_failures[provider])
            
            # Remove empty entries
            if not self._provider_failures[provider]:
                del self._provider_failures[provider]
        
        # Clean up old degradation events
        original_event_count = len(self._degradation_events)
        self._degradation_events = [
            e for e in self._degradation_events
            if e.timestamp > cutoff_time
        ]
        removed_count += original_event_count - len(self._degradation_events)
        
        if removed_count > 0:
            logger.debug(f"Cleaned up {removed_count} old failure records and events")
        
        return removed_count
    
    def reset_provider_failures(self, provider: str) -> None:
        """
        Reset failure tracking for a specific provider.
        
        Args:
            provider: Name of the provider to reset.
        """
        if provider in self._provider_failures:
            del self._provider_failures[provider]
        
        self._unavailable_providers.discard(provider)
        self._permanently_failed_providers.discard(provider)
        
        if provider in self._recovery_attempts:
            del self._recovery_attempts[provider]
        
        logger.info(f"Reset failure tracking for provider {provider}")
    
    def reset_all_failures(self) -> None:
        """Reset all failure tracking."""
        self._provider_failures.clear()
        self._unavailable_providers.clear()
        self._permanently_failed_providers.clear()
        self._recovery_attempts.clear()
        self._degradation_events.clear()
        
        self._stats = {
            'total_failures': 0,
            'providers_marked_unavailable': 0,
            'fallbacks_used': 0,
            'recoveries': 0
        }
        
        logger.info("Reset all failure tracking")
    
    def _get_recent_failures(self, provider: str, 
                           time_window_minutes: int = 60) -> List[ProviderFailure]:
        """
        Get recent failures for a provider within a time window.
        
        Args:
            provider: Name of the provider.
            time_window_minutes: Time window in minutes to consider.
            
        Returns:
            List of recent failures.
        """
        if provider not in self._provider_failures:
            return []
        
        cutoff_time = datetime.now() - timedelta(minutes=time_window_minutes)
        
        return [
            f for f in self._provider_failures[provider]
            if f.timestamp > cutoff_time
        ]
    
    def _should_attempt_recovery(self, provider: str) -> bool:
        """
        Check if enough time has passed to attempt provider recovery.
        
        Args:
            provider: Name of the provider.
            
        Returns:
            True if recovery should be attempted, False otherwise.
        """
        if provider not in self._recovery_attempts:
            return True
        
        last_attempt = self._recovery_attempts[provider]
        time_since_attempt = datetime.now() - last_attempt
        
        return time_since_attempt.total_seconds() >= self.recovery_timeout