import unittest
import monitor

SHOP = {'url': 'https://onexplayerstore.com/products/f1pro', 'seller': 'ONEXPLAYER official', 'condition': 'new', 'shipping': 0, 'kind': 'shopify'}

class DealsTest(unittest.TestCase):
    def test_exact_model(self):
        self.assertEqual(monitor.product_model('OneXFly F1 Pro OLED AMD AI 9 HX 370 - 32G +1TB'), 'onexfly_f1_pro_hx370_32')
        self.assertIsNone(monitor.product_model('OneXFly F1 Pro 8840U - 32G +1TB'))
        self.assertIsNone(monitor.product_model('OneXFly F1 Pro HX 365 - 32G +1TB'))
        self.assertEqual(monitor.product_model('Legion Go 2 Z2 Extreme 32GB OLED'), 'legion_go_2_z2e_32')
        self.assertIsNone(monitor.product_model('Legion Go 2 AMD Z2 32GB OLED'))
        self.assertEqual(monitor.product_model('ROG Xbox Ally X20 (2026) RC74XA OLED'), 'rog_xbox_ally_x20')
        self.assertIsNone(monitor.product_model('ROG Xbox Ally X (2025) 24GB'))
        self.assertIsNone(monitor.product_model('Steam Deck OLED 1TB'))
        self.assertEqual(monitor.product_model('Steam Deck OLED 512GB'), 'steam_deck_oled_512')
        self.assertIsNone(monitor.product_model('ZOTAC ZONE case replacement'))

    def test_shopify_variants_never_use_starting_price(self):
        product = {'title': 'OneXFly F1 Pro OLED', 'variants': [
            {'id': 1, 'public_title': 'AMD 8840U - 32G + 1TB', 'price': 55000, 'available': True},
            {'id': 2, 'public_title': 'AMD AI 9 HX 370 - 32G + 1TB', 'price': 83900, 'available': True},
            {'id': 3, 'public_title': 'AMD AI 9 HX 370 - 32G + 2TB', 'price': 70000, 'available': False},
        ]}
        deals = monitor.scan_shopify(SHOP, __import__('json').dumps(product))
        self.assertEqual(len(deals), 1)
        self.assertEqual(deals[0]['level'], 'exceptional')
        self.assertIn('?variant=2', deals[0]['url'])
        self.assertEqual(deals[0]['estimated_total'], 906.12)

    def test_price_with_unknown_shipping_cannot_alert(self):
        spec = dict(SHOP, shipping=None)
        offer = monitor.deal(spec, 'OneXFly F1 Pro OLED', 600.0, True, variant='AMD AI 9 HX 370 - 32G + 1TB')
        self.assertEqual(offer['level'], 'seen')
        self.assertIsNone(offer['before_tax'])

    def test_stock_required(self):
        self.assertIsNone(monitor.deal(SHOP, 'OneXFly F1 Pro OLED', 400, False, variant='AMD AI 9 HX 370 - 32G + 1TB'))

    def test_jsonld_requires_instock_usd_and_spec(self):
        spec = dict(SHOP, kind='html')
        body = '''<script type="application/ld+json">{"@type":"Product","name":"OneXFly F1 Pro OLED AMD AI 9 HX 370 32GB","offers":{"price":"820","priceCurrency":"USD","availability":"https://schema.org/OutOfStock"}}</script>'''
        self.assertEqual(monitor.scan_html(spec, body), [])
        self.assertEqual(len(monitor.scan_html(spec, body.replace('OutOfStock', 'InStock'))), 1)
        self.assertEqual(monitor.scan_html(spec, body.replace('USD', 'CAD').replace('OutOfStock', 'InStock')), [])

    def test_id_stable(self):
        a = monitor.deal(SHOP, 'OneXFly F1 Pro OLED', 800, True, variant='AMD AI 9 HX 370 - 32G + 1TB')
        b = dict(a, price=790)
        self.assertEqual(monitor.issue_marker(a), monitor.issue_marker(b))

if __name__ == '__main__':
    unittest.main()
