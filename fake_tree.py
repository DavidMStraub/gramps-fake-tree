"""Script to generate a Gramps family tree database with random data."""

import faker
import random
import uuid
import os
import datetime
from typing import Union

from gramps.gen.lib import (
    Person,
    Surname,
    Event,
    EventType,
    EventRef,
    Date,
    Family,
    ChildRef,
)


from gramps.plugins.export.exportxml import export_data as export_xml
from gramps.gen.db.utils import make_database
from gramps.gen.db import DbTxn
from gramps.gen.user import User


class FakeTree:
    """Fake Gramps tree class."""

    MAX_SIBLINGS: int = 9
    PROB_UNMARRIED: float = 0.05
    MIN_AGE: int = 55
    MAX_AGE: int = 90
    N_GEN: int = 6

    def __init__(self, locale) -> None:
        """Inititalize self."""
        self.fake = faker.Faker(locale=locale)
        self.year_now = datetime.datetime.now().year
        self.db = make_database("sqlite")
        self.db.load(":memory:")

    def export(self, filename) -> None:
        """Export the database to Gramps XML."""
        abs_path = os.path.abspath(filename)
        export_xml(self.db, abs_path, User())

    def build(self):
        person = self.add_start_person()
        self.add_family(person, recursive=True)

    def random_bool(self, probability: float):
        return random.random() <= probability

    def random_has_parents(self, n_gen: int):
        probability = 1 - n_gen / self.N_GEN
        return self.random_bool(probability)

    def random_handle(self):
        return str(uuid.uuid4())

    def random_gender(self):
        return random.choice([Person.MALE, Person.FEMALE])

    def random_date(self, year: int):
        month, day = self.fake.date("%m-%d").split("-")
        month = int(month)
        day = int(day)
        date = Date()
        date.set_yr_mon_day(year, month, day)
        return date

    def random_age(self, min_age: int = 0):
        return random.randint(min_age or self.MIN_AGE, self.MAX_AGE)

    def add_random_name(self, person: Person, surname=None):
        """Add a random name to a person object."""
        name = person.primary_name
        if person.gender == Person.MALE:
            name.first_name = self.fake.first_name_male()
        else:
            name.first_name = self.fake.first_name_female()
        _surname = Surname()
        _surname.surname = surname or self.fake.last_name()
        name.set_surname_list([_surname])

    def add_event(self, obj: Union[Family, Person], event_type: int, year_min: int, year_max: int):
        """Add and commit an event."""
        event = Event()
        event.handle = self.random_handle()
        event.type = EventType(event_type)
        year = random.randint(year_min, year_max)
        event.date = self.random_date(year)

        with DbTxn("Add event", self.db) as trans:
            self.db.add_event(event, trans)
        
        event_ref = EventRef()
        event_ref.ref = event.handle
        obj.event_ref_list.append(event_ref)

    def add_birth_date(self, person: Person, year_min: int, year_max: int):
        """Add and commit a birth date."""
        self.add_event(
            obj=person,
            event_type=EventType.BIRTH,
            year_min=year_min,
            year_max=year_max,
        )
        person.birth_ref_index = len(person.event_ref_list) - 1

    def add_death_date(self, person: Person, year_min: int, year_max: int):
        """Add and commit a death date."""
        self.add_event(
            obj=person,
            event_type=EventType.DEATH,
            year_min=year_min,
            year_max=year_max,
        )
        person.death_ref_index = len(person.event_ref_list) - 1

    def add_start_person(self) -> Person:
        """Add & commit a start person."""
        person = Person()
        person.handle = self.random_handle()
        person.gender = self.random_gender()
        self.add_random_name(person)
        self.add_birth_date(person, 1970, 2000)
        with DbTxn("Add person", self.db) as trans:
            self.db.add_person(person, trans)
        self.db.set_default_person_handle(person.handle)
        return person

    def get_birth_year(self, person: Person) -> int:
        """Get the person's birth year."""
        birth_ref = person.get_birth_ref()
        event = self.db.get_event_from_handle(birth_ref.ref)
        return event.date.get_year()

    def add_family(self, person: Person, recursive: bool = False, n_gen: int = 0):
        """Add a family (siblings and parents) to an existing person."""
        family_surname = person.primary_name.surname_list[0].surname
        birth_year = self.get_birth_year(person)

        # family
        family = Family()
        family.handle = self.random_handle()

        person.add_parent_family_handle(family.handle)

        # child ref
        child_ref = ChildRef()
        child_ref.ref = person.handle
        family.child_ref_list.append(child_ref)

        # father
        father = Person()
        father.handle = self.random_handle()
        father.add_family_handle(family.handle)
        father.gender = Person.MALE
        self.add_random_name(father, surname=family_surname)
        self.add_birth_date(father, birth_year - 40, birth_year - 20)
        family.set_father_handle(father.handle)
        father_birth_year = self.get_birth_year(father)

        # mother
        mother = Person()
        mother.handle = self.random_handle()
        mother.add_family_handle(family.handle)
        mother.gender = Person.FEMALE
        self.add_random_name(mother)
        family.set_mother_handle(mother.handle)
        self.add_birth_date(mother, birth_year - 40, birth_year - 20)
        mother_birth_year = self.get_birth_year(mother)

        marriage_year = random.randint(
            max(father_birth_year, mother_birth_year) + 18, birth_year - 1
        )
        if not self.random_bool(self.PROB_UNMARRIED):
            self.add_event(family, EventType.MARRIAGE, marriage_year, marriage_year)

        father_age = self.random_age(min_age = marriage_year - father_birth_year + 1)
        mother_age = self.random_age(min_age = marriage_year - mother_birth_year + 1)
        father_death_year = father_birth_year + father_age
        mother_death_year = mother_birth_year + mother_age
        self.add_death_date(father, father_death_year, father_death_year)
        self.add_death_date(mother, mother_death_year, mother_death_year)

        with DbTxn("Add parents", self.db) as trans:
            self.db.add_person(father, trans)
            self.db.add_person(mother, trans)
            self.db.add_family(family, trans)
            self.db.commit_person(person, trans)

        n_siblings = random.randint(0, self.MAX_SIBLINGS)
        year = marriage_year + 1
        children = []
        for _ in range(n_siblings):
            year = year + random.randint(2, 6)
            if abs(year - birth_year) < 2:
                # 2 years difference from main child
                continue
            if year > mother_birth_year + 40:
                break
            if year > mother_death_year - 2:
                break
            if year > father_death_year - 1:
                break
            child = Person()
            child.add_parent_family_handle(family.handle)
            child.handle = self.random_handle()
            child.gender = self.random_gender()
            self.add_random_name(child, surname=family_surname)
            self.add_birth_date(child, year, year)
            age = self.random_age()
            death_year = year + age
            if death_year < self.year_now:
                self.add_death_date(child, death_year, death_year)

            children.append(child)

            # child ref
            child_ref = ChildRef()
            child_ref.ref = child.handle
            family.child_ref_list.append(child_ref)

            with DbTxn("Add children", self.db) as trans:
                for child in children:
                    self.db.add_person(child, trans)
                self.db.commit_family(family, trans)

        if recursive:
            if self.random_has_parents(n_gen):
                self.add_family(father, recursive=True, n_gen=n_gen + 1)
            if self.random_has_parents(n_gen):
                self.add_family(mother, recursive=True, n_gen=n_gen + 1)


def main():
    """Main function."""
    tree = FakeTree(locale="de")
    tree.N_GEN = 9
    tree.build()
    tree.export("random_tree.gramps")


if __name__ == "__main__":
    main()
