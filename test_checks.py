"""Fixed synthetic examples for material delivery boundary conditions."""

import unittest
from datetime import date
from decimal import Decimal

from analysis import enrich, metrics


class MaterialBoundaryTests(unittest.TestCase):
    AS_OF = date(2026, 11, 13)

    def make_order(self, due_date, received_qty):
        return {
            'order_id': 'TEST-001',
            'ship_id': 'TEST-SHIP',
            'block': 'B01',
            'supplier': 'Synthetic Supplier',
            'material': 'Synthetic Material',
            'unit': 'EA',
            'ordered_qty': Decimal('100'),
            'received_qty': Decimal(str(received_qty)),
            'unit_price_krw': Decimal('1000'),
            'order_date': date(2026, 11, 1),
            'due_date': due_date,
            'critical': 'Y',
        }

    def test_due_today_is_not_overdue(self):
        rows = enrich([self.make_order(self.AS_OF, 40)], as_of=self.AS_OF)
        self.assertFalse(rows[0]['is_overdue'])
        self.assertEqual(rows[0]['status'], '미입고')
        counts = metrics(rows)
        self.assertEqual(counts['outstanding_rows'], 1)
        self.assertEqual(counts['overdue_rows'], 0)
        self.assertEqual(counts['critical_overdue_rows'], 0)
        self.assertEqual(counts['overdue_amount_krw'], Decimal('0'))

    def test_partial_receipt_leaves_sixty(self):
        rows = enrich([self.make_order(date(2026, 11, 12), 40)], as_of=self.AS_OF)
        self.assertEqual(rows[0]['outstanding_qty'], Decimal('60'))
        self.assertTrue(rows[0]['is_overdue'])
        self.assertEqual(rows[0]['status'], '지연')
        counts = metrics(rows)
        self.assertEqual(counts['outstanding_rows'], 1)
        self.assertEqual(counts['overdue_rows'], 1)
        self.assertEqual(counts['overdue_amount_krw'], Decimal('60000'))

    def test_fully_received_is_neither_outstanding_nor_overdue(self):
        # A past due date must not make a fully received order overdue.
        rows = enrich([self.make_order(date(2026, 11, 12), 100)], as_of=self.AS_OF)
        self.assertEqual(rows[0]['outstanding_qty'], Decimal('0'))
        self.assertFalse(rows[0]['is_overdue'])
        self.assertEqual(rows[0]['status'], '입고완료')
        counts = metrics(rows)
        self.assertEqual(counts['order_rows'], 1)
        self.assertEqual(counts['outstanding_rows'], 0)
        self.assertEqual(counts['overdue_rows'], 0)
        self.assertEqual(counts['critical_overdue_rows'], 0)
        self.assertEqual(counts['overdue_amount_krw'], Decimal('0'))


if __name__ == '__main__':
    unittest.main()
