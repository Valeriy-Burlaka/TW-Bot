import os
import random


class DummyRequestManager:
    """
    A stub for ReportBuilder & Map classes.
    Provides methods that returns str_HTML from hardcoded
    files instead of real server-response.
    """

    def get_reports_page(self):
        report_pages = ['report_page.html']
        report_page_file = random.choice(report_pages)
        report_page_path = os.path.join('test_html', report_page_file)
        with open(report_page_path) as f:
            html_data = f.read()
        return html_data

    def get_report(self, url):
        reports = ['single_report_green.html', 'single_report_yellow.html']

        report_file = random.choice(reports)
        report_path = os.path.join('test_html', report_file)
        with open(report_path) as f:
            html_data = f.read()
        return html_data

    def get_map_overview(self, x, y):
        files = ['map_overview_200_300.html', 'map_overview_200_327.html',
                 'map_overview_211_305.html', 'map_overview_224_324.html',
                 'map_overview_228_300.html']
        map_file = random.choice(files)
        map_path = os.path.join('test_html', map_file)
        with open(map_path) as f:
            html_data = f.read()
        return html_data