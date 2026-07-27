from dataclasses import dataclass

@dataclass
class Student:

    roll_no: str
    name: str
    department: str
    year: int
    marks: float

    def to_list(self):

        return [
            self.roll_no,
            self.name,
            self.department,
            self.year,
            self.marks
        ]