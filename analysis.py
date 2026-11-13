"""Validate and analyze educational material orders without changing the source."""

import csv
import json
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

BASE = Path(__file__).resolve().parent
AS_OF = date(2026, 11, 13)
REQUIRED = (
    'order_id', 'ship_id', 'block', 'supplier', 'material', 'unit',
    'ordered_qty', 'received_qty', 'unit_price_krw', 'order_date',
    'due_date', 'critical',
)
NUMERIC = ('ordered_qty', 'received_qty', 'unit_price_krw')


def load_material(path=BASE / 'data' / 'material_orders.csv'):
    """Load validated records; report all detected row errors before failing."""
    with Path(path).open(encoding='utf-8-sig', newline='') as source:
        reader = csv.DictReader(source)
        missing = set(REQUIRED) - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f'Missing required columns: {sorted(missing)}')
        rows = list(reader)
    errors, seen = [], set()
    for line, row in enumerate(rows, 2):
        for field in REQUIRED:
            if row.get(field) is None or not row[field].strip():
                errors.append(f'Line {line}: empty {field}')
        order_id = row.get('order_id')
        if order_id in seen:
            errors.append(f'Line {line}: duplicate order_id {order_id}')
        seen.add(order_id)
        for field in NUMERIC:
            try:
                value = Decimal(row[field])
                if not value.is_finite() or value < 0:
                    raise ValueError('must be finite and nonnegative')
                row[field] = value
            except (InvalidOperation, ValueError, TypeError):
                errors.append(f'Line {line}: invalid or negative {field}')
        if all(isinstance(row[f], Decimal) and row[f].is_finite() for f in NUMERIC):
            if row['received_qty'] > row['ordered_qty']:
                errors.append(f'Line {line}: received_qty exceeds ordered_qty')
        for field in ('order_date', 'due_date'):
            try:
                row[field] = date.fromisoformat(row[field])
            except (ValueError, TypeError):
                errors.append(f'Line {line}: invalid {field}')
        if row['critical'] not in ('Y', 'N'):
            errors.append(f'Line {line}: critical must be Y or N')
        if row['unit'] not in ('KG', 'M', 'EA'):
            errors.append(f'Line {line}: unsupported unit')
    if errors:
        raise ValueError('\n'.join(errors))
    return rows


def enrich(rows, as_of=AS_OF):
    """Calculate per-order balances and strictly-before-date overdue status."""
    result = []
    for source in rows:
        row = dict(source)
        row['outstanding_qty'] = row['ordered_qty'] - row['received_qty']
        row['is_overdue'] = row['due_date'] < as_of and row['outstanding_qty'] > 0
        row['status'] = '지연' if row['is_overdue'] else ('미입고' if row['outstanding_qty'] > 0 else '입고완료')
        row['overdue_amount_krw'] = (
            row['outstanding_qty'] * row['unit_price_krw']
            if row['is_overdue'] else Decimal(0)
        )
        result.append(row)
    return result


def metrics(rows):
    """Aggregate row counts and currency, never mixed-unit quantities."""
    return {
        'order_rows': len(rows),
        'outstanding_rows': sum(r['outstanding_qty'] > 0 for r in rows),
        'overdue_rows': sum(r['is_overdue'] for r in rows),
        'critical_overdue_rows': sum(r['is_overdue'] and r['critical'] == 'Y' for r in rows),
        'overdue_amount_krw': sum((r['overdue_amount_krw'] for r in rows), Decimal(0)),
    }


def supplier_summary(rows):
    """Return one summary per supplier with counts and KRW amounts only."""
    suppliers = sorted({r['supplier'] for r in rows})
    return [{'supplier': supplier, **metrics([r for r in rows if r['supplier'] == supplier])}
            for supplier in suppliers]


def json_number(value):
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    raise TypeError(f'Unsupported JSON value: {type(value)}')


def write_csv(path, rows, fields):
    with path.open('w', encoding='utf-8-sig', newline='') as target:
        writer = csv.DictWriter(target, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main():
    rows = enrich(load_material())
    result = {'as_of': AS_OF.isoformat(), **metrics(rows)}
    output = BASE / 'outputs'
    output.mkdir(exist_ok=True)
    (output / 'material_metrics.json').write_text(
        json.dumps(result, ensure_ascii=False, indent=2, default=json_number) + '\n',
        encoding='utf-8',
    )
    summary = supplier_summary(rows)
    write_csv(output / 'supplier_summary.csv', summary, ['supplier', *metrics([])])
    fields = [*REQUIRED, 'outstanding_qty', 'is_overdue', 'status', 'overdue_amount_krw']
    write_csv(output / 'overdue_orders.csv', [r for r in rows if r['is_overdue']], fields)
    print(json.dumps(result, ensure_ascii=False, indent=2, default=json_number))
    print('Validation passed; wrote 3 output files.')


if __name__ == '__main__':
    main()
