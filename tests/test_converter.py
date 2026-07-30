import unittest

from yummysoup2paprika.converter import html_to_text, ingredients_to_text, clean_categories


class ConverterTextTests(unittest.TestCase):
    def test_photo_reference_conversion(self):
        self.assertEqual(html_to_text("Mix. [2] Bake. [10]"), "Mix. [photo:2] Bake. [photo:10]")

    def test_bold_number_spacing(self):
        self.assertEqual(html_to_text("<b>1.</b>Mince the shallot"), "**1.** Mince the shallot")

    def test_bold_number_internal_space(self):
        self.assertEqual(html_to_text("<b>2. </b>Cook"), "**2.** Cook")

    def test_categories_are_deduplicated(self):
        self.assertEqual(clean_categories("Dessert; Cookies; dessert", "Italian"), ["Dessert", "Cookies", "Italian"])

    def test_ingredients_openstep(self):
        raw = '({quantity = "2"; measurement = cups; name = flour; method = sifted;}, {isGroupTitle = 1; name = Sauce;})'
        self.assertEqual(ingredients_to_text(raw), "2 cups flour, sifted\nSAUCE")


if __name__ == "__main__":
    unittest.main()
