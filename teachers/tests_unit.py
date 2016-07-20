from datetime import datetime, timedelta

from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from mixer.backend.django import mixer

import lessons.models as lessons
from elk.utils.test import test_teacher
from teachers.models import Teacher, WorkingHours
from timeline.models import Entry as TimelineEntry


class TestFreeSlots(TestCase):
    def setUp(self):
        self.teacher = test_teacher()

        mixer.blend(WorkingHours, teacher=self.teacher, weekday=0, start='13:00', end='15:00')  # monday
        mixer.blend(WorkingHours, teacher=self.teacher, weekday=1, start='17:00', end='19:00')  # thursday

    def test_working_hours_for_date(self):
        """
        Get datetime.datetime objects for start and end working hours
        """
        working_hours_monday = WorkingHours.objects.for_date(teacher=self.teacher, date='2016-07-18')
        self.assertIsNotNone(working_hours_monday)
        self.assertEqual(working_hours_monday.start.strftime('%Y-%m-%d %H:%M'), '2016-07-18 13:00')
        self.assertEqual(working_hours_monday.end.strftime('%Y-%m-%d %H:%M'), '2016-07-18 15:00')

        working_hours_wed = WorkingHours.objects.for_date(teacher=self.teacher, date='2016-07-20')
        self.assertIsNone(working_hours_wed)  # should not throw DoesNotExist

    def test_get_free_slots(self):
        """
        Simple unit test for fetching free slots
        """
        slots = self.teacher.find_free_slots(date='2016-07-18')
        self.assertEquals(len(slots), 4)

        def time(slot):
            return slot.strftime('%H:%M')

        self.assertEqual(time(slots[0]), '13:00')
        self.assertEqual(time(slots[-1]), '14:30')

        slots = self.teacher.find_free_slots(date='2016-07-18', period=timedelta(minutes=20))
        self.assertEquals(len(slots), 6)
        self.assertEqual(time(slots[0]), '13:00')
        self.assertEqual(time(slots[1]), '13:20')
        self.assertEqual(time(slots[-1]), '14:40')

        slots = self.teacher.find_free_slots(date='2016-07-20')
        self.assertIsNone(slots)  # should not throw DoesNotExist

    def test_get_free_slots_event_bypass(self):
        """
        Add an event and check that get_free_slots should not return any slot,
        overlapping with it
        """
        entry = TimelineEntry(teacher=self.teacher,
                              lesson=mixer.blend(lessons.OrdinaryLesson),
                              start=datetime(2016, 7, 18, 14, 0),
                              end=datetime(2016, 7, 18, 14, 30),
                              )
        entry.save()
        slots = self.teacher.find_free_slots(date='2016-07-18')
        self.assertEquals(len(slots), 3)

    def test_get_free_slots_offset_event_bypass(self):
        """
        Add event with an offset, overlapping two time slots. Should return
        two timeslots less, then normal test_get_free_slots().
        """
        entry = TimelineEntry(teacher=self.teacher,
                              lesson=mixer.blend(lessons.OrdinaryLesson),
                              start=datetime(2016, 7, 18, 14, 10),
                              end=datetime(2016, 7, 18, 14, 40)
                              )
        entry.save()
        slots = self.teacher.find_free_slots(date='2016-07-18')
        self.assertEquals(len(slots), 2)

    def test_free_slots_for_event(self):
        """
        Test for getting free time slots for a certain event type.
        """
        master_class = mixer.blend(lessons.MasterClass, host=self.teacher)
        entry = TimelineEntry(teacher=self.teacher,
                              lesson=master_class,
                              start=datetime(2016, 7, 18, 14, 10),
                              end=datetime(2016, 7, 18, 14, 40)
                              )
        entry.save()
        lesson_type = ContentType.objects.get_for_model(master_class)

        slots = self.teacher.find_free_slots(date='2016-07-18', lesson_type=lesson_type)
        self.assertEquals(len(slots), 1)

        slots = self.teacher.find_free_slots(date='2016-07-20', lesson_type=lesson_type)
        self.assertEquals(len(slots), 0)  # there is no master classes, planned on 2016-07-20

    def test_two_teachers_for_single_slot(self):
        """
        Check if find_free_slots returns only slots of selected teacher
        """
        other_teacher = test_teacher()
        master_class = mixer.blend(lessons.MasterClass, host=other_teacher)
        entry = TimelineEntry(teacher=other_teacher,
                              lesson=master_class,
                              start=datetime(2016, 7, 18, 14, 10),
                              end=datetime(2016, 7, 18, 14, 40)
                              )
        entry.save()
        lesson_type = ContentType.objects.get_for_model(master_class)

        slots = self.teacher.find_free_slots(date='2016-07-18', lesson_type=lesson_type)
        self.assertEquals(len(slots), 0)  # should not return anything — we are checking slots for self.teacher, not other_teacher

    def test_find_teacher_by_date(self):
        """
        Find a teacher that can work for distinct date without a specific event
        """
        free_teachers = Teacher.objects.find_free(date='2016-07-18')
        self.assertEquals(free_teachers[0], self.teacher)

        free_teachers = Teacher.objects.find_free(date='2017-07-20')
        self.assertEquals(len(free_teachers), 0)  # no one works on wednesdays

    def test_get_teachers_by_lesson_type(self):
        """
        Add two timeline entries for two teachers and find their slots by
        lesson_type
        """
        second_teacher = test_teacher()
        first_master_class = mixer.blend(lessons.MasterClass, host=self.teacher)
        second_master_class = mixer.blend(lessons.MasterClass, host=second_teacher)

        first_entry = TimelineEntry(teacher=self.teacher,
                                    lesson=first_master_class,
                                    start=datetime(2016, 7, 18, 14, 10),
                                    end=datetime(2016, 7, 18, 14, 40)
                                    )
        first_entry.save()

        second_entry = TimelineEntry(teacher=second_teacher,
                                     lesson=second_master_class,
                                     start=datetime(2016, 7, 18, 14, 10),
                                     end=datetime(2016, 7, 18, 14, 40)
                                     )
        second_entry.save()
        lesson_type = ContentType.objects.get_for_model(first_master_class)
        free_teachers = Teacher.objects.find_free(date='2016-07-18', lesson_type=lesson_type)
        self.assertEquals(len(free_teachers), 2)

        free_teachers = Teacher.objects.find_free(date='2016-07-20', lesson_type=lesson_type)
        self.assertEquals(len(free_teachers), 0)  # there is no master classes. planned on 2016-07-20


class TestSlotsIterable(TestCase):
    def _generate_slots(self):
        teacher = test_teacher()
        mixer.blend(WorkingHours, teacher=teacher, weekday=0, start='13:00', end='15:00')
        return teacher.find_free_slots(date='2016-07-18')

    def test_as_dict(self):
        slots = self._generate_slots()
        slots_list = slots.as_dict()
        self.assertEquals(len(slots_list), 4)
        self.assertEquals(slots_list[0], '13:00')
        self.assertEquals(slots_list[-1], '14:30')