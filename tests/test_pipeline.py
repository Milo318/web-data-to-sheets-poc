from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from web_data_pipeline.pipeline import load_products, run_pipeline
from web_data_pipeline.scraper import parse_products


FIXTURES = Path(__file__).parents[1] / "data" / "mock"


class PipelineTests(unittest.TestCase):
    def test_parser_normalizes_values(self) -> None:
        html = '<article class="product" data-sku="A-1"><h2>Desk Lamp</h2><span class="category">Office</span><span class="price">€49.90</span><span class="stock">In stock</span><span class="rating">4.7</span></article>'
        product = parse_products(html)[0]
        self.assertEqual(product.sku, "A-1")
        self.assertEqual(str(product.price_eur), "49.90")
        self.assertTrue(product.in_stock)

    def test_duplicate_sku_is_resolved_deterministically(self) -> None:
        products, duplicate_count = load_products(FIXTURES.glob("*.html"))
        self.assertEqual(len(products), 11)
        self.assertEqual(duplicate_count, 1)
        self.assertEqual(next(p for p in products if p.sku == "OF-104").source, "supplier-b.html")

    def test_pipeline_writes_csv_and_xlsx(self) -> None:
        with TemporaryDirectory() as directory:
            output = Path(directory)
            summary = run_pipeline(FIXTURES, output)
            self.assertEqual(summary["unique_products"], 11)
            self.assertTrue((output / "products.csv").exists())
            self.assertTrue((output / "products.xlsx").exists())


if __name__ == "__main__":
    unittest.main()
