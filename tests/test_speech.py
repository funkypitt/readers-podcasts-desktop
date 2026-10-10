"""What was said: the programs' answers read back, the passages handed to the translator, the
small book that leaves for the library."""
import importlib.util
import io
import json
import os
import unittest
import zipfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("rp", os.path.join(HERE, "readers_podcasts.py"))
rp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rp)

LINES = [(0, 900, "Bonjour & bienvenue."), (1000, 2000, "On parle <ici> de l'été."), (5000, 6000, "Second paragraphe.")]


class Heard(unittest.TestCase):
    def test_faster_whisper(self):
        rows = ['{"d": 12.5}', '{"a": 0.0, "b": 1.5, "t": " faux départ"}', '{"again": "CUDA failed"}', "not json",
                '{"d": 12.5}', '{"a": 0.0, "b": 2.25, "t": " Bonsoir à tous."}', '{"a": 2.5, "b": 4.0, "t": "  "}',
                '{"a": 4.0, "b": 6.0, "t": "Ce soir."}', '{"lang": "fr"}']
        self.assertEqual(rp.parse_faster(rows), ("fr", [(0, 2250, "Bonsoir à tous."), (4000, 6000, "Ce soir.")]))

    def test_whisper_cpp(self):
        data = {"result": {"language": "fr"}, "transcription": [
            {"offsets": {"from": 0, "to": 2240}, "text": " Bonsoir à tous."}, {"offsets": {"from": 2240, "to": 2300}, "text": " "}]}
        self.assertEqual(rp.parse_whisper_cpp(data), ("fr", [(0, 2240, "Bonsoir à tous.")]))

    def test_openai_whisper(self):
        data = {"language": "fr", "segments": [{"start": 0.0, "end": 2.24, "text": " Bonsoir à tous."}, {"start": 3, "end": 4, "text": ""}]}
        self.assertEqual(rp.parse_openai(data), ("fr", [(0, 2240, "Bonsoir à tous.")]))

    def test_the_time_a_program_prints_as_it_goes(self):
        self.assertEqual(rp.stamp_end_ms("[00:01.000 --> 00:05.500]  Bonsoir"), 5500)
        self.assertEqual(rp.stamp_end_ms("[00:00:01.000 --> 01:02:03.250]  x"), 3723250)
        self.assertIsNone(rp.stamp_end_ms("Detecting language"))

    def test_paragraphs_on_a_pause(self):
        self.assertEqual(rp.transcript_text(LINES), "Bonjour & bienvenue. On parle <ici> de l'été.\n\nSecond paragraphe.")
        self.assertEqual([len(p) for p in rp.transcript_paragraphs(LINES + [(6100, 7000, " ")])], [2, 1])


class Translating(unittest.TestCase):
    def test_passages_of_about_seven_hundred_characters_keep_their_times(self):
        lines = [(i * 1000, i * 1000 + 900, "mot " * 30) for i in range(20)]
        blocks = rp.group_blocks(lines)
        self.assertEqual((blocks[0][0], blocks[0][1]), (0, 5900))
        self.assertTrue(all(len(t) >= rp.BLOCK_CHARS for _a, _b, t in blocks[:-1]))
        self.assertEqual(blocks[-1][1], 19900)
        self.assertEqual(sum(t.count("mot") for _a, _b, t in blocks), 600)

    def test_an_answer_is_cleaned_and_judged(self):
        self.assertEqual(rp.clean_answer('<think>hm</think>\nTRADUCTION EN FRANÇAIS : "Bonsoir à tous."'), "Bonsoir à tous.")
        self.assertTrue(rp.acceptable("Good evening to all of you.", "Bonsoir à toutes et à tous."))
        self.assertFalse(rp.acceptable("Good evening.", "good evening."))               # handed back
        self.assertFalse(rp.acceptable("Good evening to all of you, dear friends.", "Oui."))    # something else
        self.assertFalse(rp.acceptable("Good evening.", ""))

    def test_the_words_asked_are_the_phone_s(self):
        self.assertEqual(set(rp._ASK), set(rp._STRICT))
        self.assertEqual(set(rp._ASK), set(rp.TRANSLATE_LANGUAGES))
        for table in (rp._ASK, rp._STRICT):
            for text in table.values():
                self.assertEqual(text.count("%s"), 1)
                self.assertNotIn("%1", text)

    def test_the_model_that_translates(self):
        models = [("qwen3:4b", 1), ("gemma3:12b", 3), ("gemma3:4b", 2), ("mistral-small:latest", 4)]
        self.assertEqual(rp.pick_model(models), "gemma3:4b")
        self.assertEqual(rp.pick_model(models, "mistral-small:latest"), "mistral-small:latest")
        self.assertEqual(rp.pick_model(models, "gone:1b"), "gemma3:4b")
        self.assertEqual(rp.pick_model([("llama3:8b", 1)]), "llama3:8b")
        self.assertEqual(rp.pick_model([]), "")

    def test_a_translation_run_with_a_model_that_fumbles(self):
        asked = []

        class Answer:
            def __init__(self, text):
                self.text = text

            def raise_for_status(self):
                pass

            def json(self):
                return {"response": self.text}

        def post(url, json=None, timeout=None):
            if "prompt" not in json:
                asked.append("unload")
                return Answer("")
            asked.append(json["prompt"][:12])
            # the first passage: fumbled, then translated at the second asking; the second: fumbled twice
            n = len([a for a in asked if a != "unload"])
            return Answer("Good evening. " * 50 if n == 2 else "Non.")

        lines = [(i * 1000, i * 1000 + 900, "Bonsoir à tous. ") for i in range(88)]
        original, rp.requests.post = rp.requests.post, post
        try:
            seen = []
            out = rp.translate(lines, "en", "gemma3:4b", seen.append, lambda: False)
        finally:
            rp.requests.post = original
        self.assertEqual(len(out), 2)
        self.assertTrue(out[0][2].startswith("Good evening."))
        self.assertTrue(out[1][2].startswith("Bonsoir à tous."))          # kept as it was said
        self.assertEqual((out[0][0], out[1][1]), (0, 87900))
        self.assertEqual(asked[-1], "unload")
        self.assertEqual(seen, [0, 50])


class Library(unittest.TestCase):
    def test_a_transcript_is_a_book_readers_books_can_read(self):
        data = rp.epub_build("abc", "Épisode 12 : « l'été »", "La Chaîne", "fr", "La Chaîne · 3 mars 2026", rp.transcript_text(LINES))
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            self.assertEqual(z.namelist(), ["mimetype", "META-INF/container.xml", "OEBPS/content.opf", "OEBPS/nav.xhtml", "OEBPS/text.xhtml"])
            self.assertEqual(z.getinfo("mimetype").compress_type, zipfile.ZIP_STORED)
            opf, page = z.read("OEBPS/content.opf").decode(), z.read("OEBPS/text.xhtml").decode()
        self.assertIn("<dc:title>Épisode 12 : « l'été »</dc:title>", opf)
        self.assertIn("<dc:creator>La Chaîne</dc:creator>", opf)
        self.assertIn('<p class="author">La Chaîne · 3 mars 2026</p>', page)
        self.assertIn("<p>Bonjour &amp; bienvenue. On parle &lt;ici&gt; de l'été.</p>\n<p>Second paragraphe.</p>", page)
        self.assertEqual(data, rp.epub_build("abc", "Épisode 12 : « l'été »", "La Chaîne", "fr", "La Chaîne · 3 mars 2026", rp.transcript_text(LINES)))

    def test_names_and_what_is_still_to_send(self):
        self.assertEqual(rp.book_file_name('Un: titre / avec "tout"?.'), "Un titre avec tout")
        self.assertEqual(rp.book_file_name(" .. "), "untitled")
        self.assertEqual(len(rp.book_file_name("a" * 300)), 120)
        self.assertEqual([rp.shelf_wanted(e) for e in ({}, {"transcript": True}, {"transcript": True, "translation": "fr"})], ["", "t", "t+fr"])
        self.assertFalse(rp.shelf_configured({"shelf_url": "https://d/", "shelf_username": "u"}))
        self.assertTrue(rp.shelf_configured({"shelf_url": "https://d/", "shelf_username": "u", "shelf_password": "p"}))

    def test_the_library_account_from_a_credentials_file(self):
        self.assertIsNone(rp.shelf_account('{"hello": 1}'))
        self.assertIsNone(rp.shelf_account("not json"))
        both = {"format": "readers-credentials", "readers-books": {"url": "https://d/", "username": "u", "password": "p"},
                "readers-notes": {"server": "https://n/"}}
        self.assertEqual(rp.shelf_account(json.dumps(both)), ("https://d/", "u", "p"))
        notes = {"format": "readers-credentials", "readers-notes": {"server": "https://n/", "folder": "Notes", "username": "u", "password": "p"}}
        self.assertEqual(rp.shelf_account(json.dumps(notes))[0], "https://n/")
        self.assertEqual(rp.shelf_account(json.dumps({"format": "readers-credentials", "readers-tasks": {"url": "https://t/"}})), ("", "", ""))


if __name__ == "__main__":
    unittest.main()
