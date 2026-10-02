import unittest

import helpers  # noqa: F401  добавляет server/ в путь
from topics import DEFAULT_TOPIC, TOPICS, classify


class ClassifyTest(unittest.TestCase):
    def test_examples(self):
        cases = {
            "Как остановить паническую атаку": "Панические атаки",
            "ВСД: почему колотится сердце": "ВСД",
            "Навязчивые мысли при неврозе": "Невроз",
            "Катастрофическое мышление": "Работа с мыслями",
            "Откуда берётся тревога": "Тревога",
            "Дыхательная техника на каждый день": "Самопомощь",
            "Ответы на вопросы": DEFAULT_TOPIC,
            "": DEFAULT_TOPIC,
        }
        for title, topic in cases.items():
            with self.subTest(title=title):
                self.assertEqual(classify(title), topic)

    def test_result_is_always_known_topic(self):
        for title in ["абв", "ПАНИКА", "страх и всд"]:
            self.assertIn(classify(title), TOPICS)


if __name__ == "__main__":
    unittest.main()
