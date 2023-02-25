@dataclass(frozen=True)
class Sequence:
    body: str

    prefix: str = "\x1b["
    suffix: str = "m"

    def __str__(self) -> str:
        if body == "":
            return ""

        return self.prefix + self.body + self.suffix

    @classmethod
    def empty(cls) -> Sequence:
        """Returns an empty sequence."""

        return cls("")

    @property
    def unsetter(self) -> str:
        raise NotImplementedError()


class CSIType(Enum):
    MODE = "mode"
    COLOR_FORE = "color_fore"
    COLOR_BACK = "color_back"


@dataclass(frozen=True)
class CSI(Sequence):
    stype: CSIType = CSIType.MODE

    @property
    def unsetter(self) -> str:
        if self.is_color():
            return UNSETTERS["COLOR_FORE" if self.is_foreground() else "COLOR_BACK"]

        return UNSETTERS[self.body]

    def is_foreground(self) -> bool:
        return self.body.startswith("4")
