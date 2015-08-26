#!/usr/bin/env python
from time import sleep
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.support.ui import Select
from selenium.webdriver.common.keys import Keys


class LoginError(Exception):
    pass

class RegistrationError(Exception):
    pass


def login_required(func_to_wrap):
    def check_logged_in(cls, *f_args, **f_kwargs):
        if getattr(cls, 'is_logged_in', False):
            func_to_wrap(cls, *f_args, **f_kwargs)
        else:
            func_name = func_to_wrap.__name__
            msg = 'You must be logged in to invoke `{0}`'.format(func_name)
            raise LoginError(msg)
    return check_logged_in


def select_term_required(func_to_wrap):
    def check_term_selected(cls, *f_args, **f_kwargs):
        if getattr(cls, 'term_selected', False):
            func_to_wrap(cls, *f_args, **f_kwargs)
        else:
            func_name = func_to_wrap.__name__
            msg = 'You must select a term to invoke `{0}`'.format(func_name)
            raise LoginError(msg)
    return check_term_selected


class Loris(object):

    def __init__(self):
        self.driver = webdriver.PhantomJS('phantomjs', service_log_path='/tmp/ghostdriver.log')
        self.is_logged_in = False
        self.term_selected = False

    def quit(self):
        self.driver.quit()

    def login(self, student_num, pin):
        d = self.driver
        # login page
        d.get('https://loris.wlu.ca/ssb_prod/twbkwbis.P_ValLogin')
        # enter student number
        uid_input = d.find_element_by_id('UserID')
        uid_input.send_keys(str(student_num))
        # enter password
        pin_input = d.find_element_by_name('PIN')
        pin_input.send_keys(str(pin))
        # submit form
        form = d.find_element_by_name('loginform')
        form.submit()
        if 'Authorization Failure' in d.page_source:
            raise LoginError('got Authorization Failure')
        self.is_logged_in = True

    @login_required
    def select_term(self, term):
        d = self.driver
        d.get('https://loris.wlu.ca/ssb_prod/bwskflib.P_SelDefTerm')
        dropdown = Select(d.find_element_by_id('term_id'))
        dropdown.select_by_value(term)
        d.find_elements_by_css_selector('form')[1].submit()
        self.term_selected = True

    def _get_courses_info_if_on_register_page(self):
        d = self.driver
        def get_course_info(c):
            status = c.find_element_by_css_selector('td:nth-child(1)').text
            reg_status, date_str = status.split(' on ')
            date = datetime.strptime(date_str, "%b %d,%Y")
            crn = c.find_element_by_css_selector('td:nth-child(3)').text
            subj = c.find_element_by_css_selector('td:nth-child(4)').text
            crscode = c.find_element_by_css_selector('td:nth-child(5)').text
            title = c.find_element_by_css_selector('td:nth-child(10)').text
            return {
                'status': reg_status.strip(),
                'date': date,
                'crn': crn.strip(),
                'subject': subj.strip(),
                'course_code': crscode.strip(),
                'title': title.strip()
            }
        courses = d.find_elements_by_css_selector(
            'table[summary*="Current Schedule"] tbody tr:not(:first-child)'
        )
        return [get_course_info(c) for c in courses]

    def _print_schedule_if_on_register_page(self, courses_info):
        def sort(info):
            return info['subject'] + info['course_code']

        def print_course(c):
            s = "{0:28} {1:2}{2:3} {3:6} {4}"
            print s.format(
                "{0} on {1}".format(c['status'], c['date'].strftime("%b %d, %Y")),
                c['subject'], c['course_code'],
                "(%s)" % c['crn'], c['title']
            )

        enrolled = []
        rest = []
        for c in courses_info:
            if c['status'] == '**Enrolled**': enrolled.append(c)
            else: rest.append(c)

        for c in enrolled: print_course(c)
        print ""
        for c in rest: print_course(c)

    @select_term_required
    def register_course(self, crn=540):
        d = self.driver
        d.get('https://loris.wlu.ca/ssb_prod/bwskfreg.P_AltPin')
        crn_input_element = d.find_element_by_id('crn_id1')
        crn_input_element.send_keys(str(crn))
        submit_changes = d.find_element_by_css_selector(
            'input[value*="Submit Changes"]'
        )
        submit_changes.click()
        sleep(2)

        if 'Registration Add Errors' in d.page_source:
            err = d.find_element_by_css_selector(
                'table[summary*="Registration Errors"] tr:not(:first-child) td:first-child'
            )
            raise RegistrationError(err.text)

        courses_info = self._get_courses_info_if_on_register_page()
        course_info = [c for c in courses_info if c['crn'] == str(crn)]
        assert len(course_info) == 1, 'Course matching CRN {0} was not found'.format(crn)
        course_info = course_info[0]

        if '**Enrolled**' in course_info['status']:
            # hooray!
            self._print_schedule_if_on_register_page(courses_info)

        else:
            msg = 'Something went wrong for course {0}. Status is {1}'\
                    .format(crn, course_info['status'])
            raise RegistrationError(msg)

    @select_term_required
    def print_schedule(self):
        d = self.driver
        d.get('https://loris.wlu.ca/ssb_prod/bwskfreg.P_AltPin')
        courses_info = self._get_courses_info_if_on_register_page()
        self._print_schedule_if_on_register_page(courses_info)


if __name__ == '__main__':
    import sys
    from credentials import STUDENT_NUM, PIN

    loris = Loris()

    # fall 2015: 201509
    # winter 2016: 201601
    # spring 2016: 201605
    TERM = '201509'

    loris.login(STUDENT_NUM, PIN)
    loris.select_term(TERM)

    if len(sys.argv) == 1: # no args provided
        print "Usage:"
        print "  loris [CRN]  -- will attempt to register for given CRN\n"
        loris.print_schedule()
        loris.quit()
        sys.exit()

    CRN = sys.argv[1] if len(sys.argv) >= 2 else '540'

    print "Attempting to register for CRN {0} in term {1}".format(CRN.strip(), TERM)

    try:
        loris.register_course(CRN)
    except RegistrationError as e:
        # only wanna quit if it fails as per usual
        loris.quit()
        print "Registration Error: {0}".format(str(e))
