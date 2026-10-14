from batch_processor import process_lines

def summarize(lines):
    result = process_lines(lines)
    return {
        'accepted_count': len(result.accepted),
        'errors': [{'line_number': e.line_number, 'code': e.code, 'message': e.message} for e in result.errors],
        'orders': [{'order_id': order, 'total': format(total, '.2f')} for order, total in result.totals.items()],
    }
