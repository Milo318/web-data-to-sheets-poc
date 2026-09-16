from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from web_data_pipeline.pipeline import load_products, run_pipeline
from web_data_pipeline.scraper import parse_products
from web_data_pipeline.autonomy import build_and_promote_adapter
from web_data_pipeline.autonomous_benchmark import generate_cases


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

    def test_ai_mapping_is_canary_validated(self) -> None:
        case = generate_cases(1)[0]
        outcome = build_and_promote_adapter(case.sample_html, case.canary_html, case.truth)
        self.assertTrue(outcome.approved)
        self.assertEqual(outcome.records_parsed, 4)

    def test_invalid_mapping_self_repairs_without_approval(self) -> None:
        case = generate_cases(1)[0]
        outcome = build_and_promote_adapter(case.sample_html, case.canary_html, {"name": ".wrong"})
        self.assertTrue(outcome.approved)
        self.assertEqual(outcome.source, "deterministic_self_repair")
        self.assertFalse(outcome.manual_approval_required)

    def test_autonomous_benchmark_has_200_layouts(self) -> None:
        cases = generate_cases(200)
        self.assertEqual(len(cases), 200)
        self.assertEqual(sum(case.challenge != "standard" for case in cases), 100)


if __name__ == "__main__":
    unittest.main()
