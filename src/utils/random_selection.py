"""
Random selection utility for resolving random option patterns in task descriptions
"""
import re
import random


def resolve_random_selection(description: str) -> str:
    """
    Resolve random selection patterns in task description.
    
    Patterns supported:
    - [yes/no] → randomly picks one option
    - [a/b/c] → randomly picks one option from multiple
    - [2,a/b/c] → randomly picks 2 options (no duplicates), formats as "a and b"
    - [a/b/[c/d]] → nested groups; innermost resolves first, then the outer
    
    Args:
        description: Task description with optional random selection patterns
        
    Returns:
        Description with all patterns resolved
    """
    if not description:
        return description
    
    # Pattern to match: [count,option1/option2/option3] or [option1/option2/option3]
    # The inner class excludes both '[' and ']' so this only matches the
    # innermost bracket group on each pass; nested groups are resolved by
    # repeatedly applying the substitution below.
    # Captures:
    # - Group 1: Optional count (number followed by comma)
    # - Group 2: Options separated by slashes
    pattern = r'\[(\d+,\s*)?([^][]+)\]'
    
    def replace_match(match):
        """Replace a single matched pattern with resolved selection"""
        count_part = match.group(1)  # e.g., "2, " or None
        options_part = match.group(2)  # e.g., "yes/no" or "a/b/c"
        
        # Parse options
        options = [opt.strip() for opt in options_part.split('/')]
        options = [opt for opt in options if opt]  # Remove empty options
        
        if not options:
            return match.group(0)  # Return original if no valid options
        
        # Handle count-based selection
        if count_part:
            # Extract count number
            count_str = count_part.rstrip(', ').strip()
            try:
                count = int(count_str)
            except ValueError:
                return match.group(0)  # Return original if count is invalid
            
            # Ensure count doesn't exceed available options
            count = min(count, len(options))
            
            if count <= 0:
                return match.group(0)  # Return original if invalid count
            
            # Randomly select count options without duplicates
            selected = random.sample(options, count)
            
            # Format as "a and b and c" or "a and b"
            if len(selected) == 1:
                return selected[0]
            elif len(selected) == 2:
                return f"{selected[0]} and {selected[1]}"
            else:
                # Format as "a, b, and c" (Oxford comma style)
                return ", ".join(selected[:-1]) + f", and {selected[-1]}"
        else:
            # Single selection - randomly pick one option
            return random.choice(options)
    
    # Repeatedly resolve innermost groups until the string stabilises so
    # nested patterns like [a/b/[c/d]] collapse from the inside out.
    # Bound the loop to guard against any pathological input that fails to
    # shrink (shouldn't happen with the regex above, but be safe).
    resolved = description
    for _ in range(32):
        next_resolved = re.sub(pattern, replace_match, resolved)
        if next_resolved == resolved:
            break
        resolved = next_resolved
    
    return resolved

