"""WWI record framing must preserve values without repeatedly copying the whole buffer."""
import io

from megasamples.sources import wwi


def test_record_reader_copies_each_buffer_linearly(monkeypatch):
    class Tracked(bytes):
        copied = 0

        def __add__(self, other):
            result = bytes.__add__(self, other)
            Tracked.copied += len(result)
            return Tracked(result)

        def __radd__(self, other):
            result = bytes.__add__(other, self)
            Tracked.copied += len(result)
            return Tracked(result)

        def __getitem__(self, key):
            result = bytes.__getitem__(self, key)
            if isinstance(key, slice):
                Tracked.copied += len(result)
                return Tracked(result)
            return result

    payload = (wwi.VAL.encode() + b"x" * 80 + wwi.ROW) * 300

    class Input(io.BytesIO):
        def read(self, size=-1):
            return Tracked(super().read(size))

    monkeypatch.setattr(wwi, "open", lambda *a: Input(payload), raising=False)
    assert list(wwi.read_rows("unused", 1, "sample")) == [["x" * 80]] * 300
    assert Tracked.copied < 4 * len(payload), "reader repeatedly copies the unconsumed buffer"


def test_record_reader_preserves_tags_and_split_terminators(tmp_path, monkeypatch):
    payload = b"\x00\x1f\x01\x1f\x01caf\xc3\xa9\x1e\n\x01end\x1f\x00\x1f\x01\x00"
    path = tmp_path / "sample.dat"
    path.write_bytes(payload)
    original_open = open

    class SmallReads:
        def __enter__(self):
            self.file = original_open(path, "rb")
            return self

        def __exit__(self, *args):
            self.file.close()

        def read(self, size):
            return self.file.read(11)  # first chunk ends with 0x1e; 0x0a arrives next

    monkeypatch.setattr(wwi, "open", lambda *a: SmallReads(), raising=False)
    assert list(wwi.read_rows(path, 3, "sample")) == [[None, "", "café"], ["end", None, "\x00"]]
