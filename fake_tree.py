"""Script to generate a Gramps family tree database with random data."""

import datetime
import glob
import os
import random
import uuid
from typing import Optional, Union

import faker
from gramps.gen.db import DbTxn
from gramps.gen.db.utils import make_database
from gramps.gen.display.name import NameDisplay
from gramps.gen.lib import (
    ChildRef,
    Date,
    Event,
    EventRef,
    EventType,
    Family,
    Media,
    MediaRef,
    Note,
    Person,
    Place,
    PlaceName,
    PlaceType,
    StyledText,
    Surname,
)
from gramps.gen.user import User
from gramps.gen.utils.file import create_checksum
from gramps.plugins.export.exportxml import XmlWriter


class FakeTree:
    """Fake Gramps tree class."""

    MAX_SIBLINGS: int = 9
    PROB_UNMARRIED: float = 0.05
    PROB_PERSON_HAS_NOTE: float = 0.5
    PROB_EVENT_HAS_NOTE: float = 0.5
    MIN_AGE: int = 55
    MAX_AGE: int = 90
    N_GEN: int = 6
    MIN_NOTE_LEN: int = 200
    MAX_NOTE_LEN: int = 2000
    NUM_PLACES: int = 50
    PROB_PERSON_RELOCATED: int = 0.2

    def __init__(self, locale, country_code: str = "US") -> None:
        """Inititalize self."""
        self.fake = faker.Faker(locale=locale)
        self.country_code = country_code
        self.year_now = datetime.datetime.now().year
        self.db = make_database("sqlite")
        self.db.load(":memory:")
        self.places = []
        self.images = set(self._get_images())
        self.db.set_mediapath(os.path.abspath("."))

    def _get_images(self):
        """Get a list of images."""
        return glob.glob("**/*.jpg", recursive=True)

    def export(self, filename) -> None:
        """Export the database to Gramps XML."""
        abs_path = os.path.abspath(filename)
        user = User()
        g = XmlWriter(self.db, user, 0, compress=False)
        g.write(abs_path)

    def build(self):
        self.add_places()
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

    def random_text(self):
        """Generate random text for a note."""
        chars = random.randint(self.MIN_NOTE_LEN, self.MAX_NOTE_LEN)
        return self.fake.text(chars)

    def random_place(self) -> Place:
        lat, lng, name, _, _ = self.fake.local_latlng(self.country_code)
        place = Place()
        place.handle = self.random_handle()
        place_type = random.choice(
            [
                PlaceType.CITY,
                PlaceType.HAMLET,
                PlaceType.LOCALITY,
                PlaceType.MUNICIPALITY,
                PlaceType.VILLAGE,
                PlaceType.TOWN,
            ]
        )
        place.set_type(PlaceType(place_type))
        place_name = PlaceName()
        place_name.set_value(name)
        place.set_name(place_name)
        place.set_latitude(lat)
        place.set_longitude(lng)
        return place

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

    def add_event(
        self,
        obj: Union[Family, Person],
        event_type: int,
        year_min: int,
        year_max: int,
        place_handle: Optional[str] = None,
    ) -> Event:
        """Add and commit an event."""
        event = Event()
        event.handle = self.random_handle()
        event.type = EventType(event_type)
        year = random.randint(year_min, year_max)
        event.date = self.random_date(year)
        if self.random_bool(self.PROB_EVENT_HAS_NOTE):
            self.add_note(event)
        if place_handle:
            event.place = place_handle

        with DbTxn("Add event", self.db) as trans:
            self.db.add_event(event, trans)

        event_ref = EventRef()
        event_ref.ref = event.handle
        obj.event_ref_list.append(event_ref)

        return event

    def add_note(self, obj):
        """Add a note to an object."""
        note = Note()
        note.handle = self.random_handle()
        text = self.random_text()
        styled_text = StyledText(text)
        note.set_styledtext(styled_text)

        with DbTxn("Add note", self.db) as trans:
            self.db.add_note(note, trans)

        obj.note_list.append(note.handle)

    def add_birth_date(
        self,
        person: Person,
        year_min: int,
        year_max: int,
        place_handle: Optional[str] = None,
    ):
        """Add and commit a birth date."""
        self.add_event(
            obj=person,
            event_type=EventType.BIRTH,
            year_min=year_min,
            year_max=year_max,
            place_handle=place_handle,
        )
        person.birth_ref_index = len(person.event_ref_list) - 1

    def add_death_date(
        self,
        person: Person,
        year_min: int,
        year_max: int,
        place_handle: Optional[str] = None,
    ):
        """Add and commit a death date."""
        self.add_event(
            obj=person,
            event_type=EventType.DEATH,
            year_min=year_min,
            year_max=year_max,
            place_handle=place_handle,
        )
        person.death_ref_index = len(person.event_ref_list) - 1

    def add_image(self, obj, folder: str, title: str, color: bool = True):
        image = ""
        for candidate_image in self.images:
            if color and folder in candidate_image and "color" in candidate_image:
                image = candidate_image
                break
            if (
                not color
                and folder in candidate_image
                and "grayscale" in candidate_image
            ):
                image = candidate_image
                break
        if not image:
            return
        # remove image from faces since we used it
        self.images = self.images - {image}

        media = Media()
        media.handle = self.random_handle()
        media.set_path(image)
        checksum = create_checksum(os.path.abspath(image))
        media.set_checksum(checksum)
        media.set_mime_type("image/jpeg")
        media.set_description(title)

        with DbTxn("Add media object", self.db) as trans:
            self.db.add_media(media, trans)

        media_ref = MediaRef()
        media_ref.set_reference_handle(media.handle)
        obj.add_media_reference(media_ref)

    def add_face(self, person: Person, color: bool = True):
        name_display = NameDisplay()
        person_name = name_display.display(person)
        return self.add_image(
            obj=person, folder="people", title=person_name, color=color
        )

    def add_family_picture(
        self, family: Family, father: Person, mother: Person, color: bool = True
    ):
        name_display = NameDisplay()
        father_name = name_display.display(father)
        mother_name = name_display.display(mother)
        title = f"{father_name} & {mother_name}"
        return self.add_image(obj=family, folder="family", title=title, color=color)

    def add_wedding_picture(
        self, event: Event, father: Person, mother: Person, color: bool = True
    ):
        name_display = NameDisplay()
        father_name = name_display.display(father)
        mother_name = name_display.display(mother)
        title = f"{father_name} & {mother_name}"
        return self.add_image(obj=event, folder="wedding", title=title, color=color)

    def add_start_person(self) -> Person:
        """Add & commit a start person."""
        person = Person()
        person.handle = self.random_handle()
        person.gender = self.random_gender()
        self.add_random_name(person)
        birth_place_handle = None
        if self.places:
            birth_place = random.choice(self.places)
            birth_place_handle = birth_place.handle
        self.add_birth_date(person, 1970, 2000, place_handle=birth_place_handle)
        self.add_note(person)
        self.add_face(person)

        with DbTxn("Add person", self.db) as trans:
            self.db.add_person(person, trans)

        self.db.set_default_person_handle(person.handle)
        return person

    def get_birth_year(self, person: Person) -> int:
        """Get the person's birth year."""
        birth_ref = person.get_birth_ref()
        event = self.db.get_event_from_handle(birth_ref.ref)
        return event.date.get_year()

    def get_birth_place_handle(self, person: Person) -> str:
        """Get the person's birth place."""
        birth_ref = person.get_birth_ref()
        event = self.db.get_event_from_handle(birth_ref.ref)
        return event.place

    def add_family(self, person: Person, recursive: bool = False, n_gen: int = 0):
        """Add a family (siblings and parents) to an existing person."""
        family_surname = person.primary_name.surname_list[0].surname
        birth_year = self.get_birth_year(person)
        birth_place_handle = self.get_birth_place_handle(person)

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
        if self.random_bool(self.PROB_PERSON_RELOCATED) and self.places:
            father_birth_place = random.choice(self.places)
            father_birth_place_handle = father_birth_place.handle
        else:
            father_birth_place_handle = birth_place_handle
        self.add_birth_date(
            father, birth_year - 40, birth_year - 20, father_birth_place_handle
        )
        family.set_father_handle(father.handle)
        father_birth_year = self.get_birth_year(father)
        if self.random_bool(self.PROB_PERSON_HAS_NOTE):
            self.add_note(father)
        if father_birth_year > 1940:
            self.add_face(father, color=True)
        elif father_birth_year > 1860:
            self.add_face(father, color=False)

        # mother
        mother = Person()
        mother.handle = self.random_handle()
        mother.add_family_handle(family.handle)
        mother.gender = Person.FEMALE
        self.add_random_name(mother)
        family.set_mother_handle(mother.handle)
        if self.random_bool(self.PROB_PERSON_RELOCATED) and self.places:
            mother_birth_place = random.choice(self.places)
            mother_birth_place_handle = mother_birth_place.handle
        else:
            mother_birth_place_handle = birth_place_handle
        self.add_birth_date(
            mother, birth_year - 40, birth_year - 20, mother_birth_place_handle
        )
        mother_birth_year = self.get_birth_year(mother)
        if self.random_bool(self.PROB_PERSON_HAS_NOTE):
            self.add_note(mother)

        if mother_birth_year > 1940:
            self.add_face(mother, color=True)
        elif mother_birth_year > 1860:
            self.add_face(mother, color=False)

        marriage_year = random.randint(
            max(father_birth_year, mother_birth_year) + 18, birth_year - 1
        )
        if not self.random_bool(self.PROB_UNMARRIED):
            marriage = self.add_event(
                family, EventType.MARRIAGE, marriage_year, marriage_year
            )
        else:
            marriage = None

        father_age = self.random_age(min_age=marriage_year - father_birth_year + 1)
        mother_age = self.random_age(min_age=marriage_year - mother_birth_year + 1)
        father_death_year = father_birth_year + father_age
        mother_death_year = mother_birth_year + mother_age
        self.add_death_date(
            father, father_death_year, father_death_year, birth_place_handle
        )
        self.add_death_date(
            mother, mother_death_year, mother_death_year, birth_place_handle
        )

        if marriage_year > 1950:
            self.add_family_picture(family, father, mother, color=True)
            if marriage:
                self.add_wedding_picture(marriage, father, mother, color=True)
        elif marriage_year > 1880:
            self.add_family_picture(family, father, mother, color=False)
            if marriage:
                self.add_wedding_picture(marriage, father, mother, color=True)

        with DbTxn("Add parents", self.db) as trans:
            self.db.add_person(father, trans)
            self.db.add_person(mother, trans)
            self.db.add_family(family, trans)
            self.db.commit_person(person, trans)
            if marriage:
                self.db.commit_event(marriage, trans)

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
            self.add_birth_date(child, year, year, birth_place_handle)
            age = self.random_age()
            death_year = year + age
            if death_year < self.year_now:
                if self.random_bool(self.PROB_PERSON_RELOCATED) and self.places:
                    death_place = random.choice(self.places)
                    death_place_handle = death_place.handle
                else:
                    death_place_handle = birth_place_handle
                self.add_death_date(child, death_year, death_year, death_place_handle)
            if self.random_bool(self.PROB_PERSON_HAS_NOTE):
                self.add_note(child)

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

    def add_places(self):
        with DbTxn("Add places", self.db) as trans:
            for _ in range(self.NUM_PLACES):
                place = self.random_place()
                self.places.append(place)
                self.db.add_place(place, trans)


def main():
    """Main function."""
    tree = FakeTree(locale="de", country_code="DE")
    tree.N_GEN = 9
    tree.build()
    tree.export("random_tree.gramps")


if __name__ == "__main__":
    main()
