"""FRED index processor for Indeed job postings analysis."""

from aredevscooked.generators.badge_generator import BadgeGenerator


class FredProcessor:
    """Process FRED index data and classify changes with badges.

    Uses the same percentage-based thresholds as headcount.
    The Indeed index is re-normalized so that 1 year ago = 100.
    """

    def __init__(self):
        self.badge_generator = BadgeGenerator()

    def calculate_percentage_change(self, current: float, baseline: float) -> float:
        """Calculate percentage change between two index values.

        Args:
            current: Current index value
            baseline: Baseline index value

        Returns:
            Percentage change (e.g., -10.5 for -10.5%)

        Raises:
            ValueError: If baseline is non-positive
        """
        if baseline <= 0:
            raise ValueError(f"Baseline must be positive: {baseline}")

        return ((current - baseline) / baseline) * 100

    def classify_change(self, percentage_change: float) -> str:
        """Classify index change into badge level.

        Reuses headcount thresholds since both are percentage-based.

        Args:
            percentage_change: Percentage change value

        Returns:
            Badge level: strong, neutral, reasonably_weak, weak, or collapsing
        """
        return self.badge_generator.get_headcount_badge(percentage_change)
