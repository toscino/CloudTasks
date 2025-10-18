# Test the flattening logic
def flatten_themes(themes):
    flat_list = []
    for theme in themes:
        if isinstance(theme, list):
            flat_list.extend(flatten_themes(theme))
        elif theme and str(theme).strip():  # Only add non-empty themes
            flat_list.append(str(theme).strip())
    return flat_list

# Test with the problematic data from the debug output
test_themes = [['Porn', []], ['Finish on a Karleigh\'s Specific Body Part', ['Tits']]]
result = flatten_themes(test_themes)
print(f'Input: {test_themes}')
print(f'Output: {result}')
print(f'Join result: {", ".join(result)}')

# Test with more complex nested structure
complex_test = [['Karleigh Orgasms Twice', []], ['Karleigh Shows Off', ['Flash']]]
complex_result = flatten_themes(complex_test)
print(f'\nComplex Input: {complex_test}')
print(f'Complex Output: {complex_result}')
print(f'Complex Join result: {", ".join(complex_result)}')
