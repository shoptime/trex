from furl import furl

class Pager():
    first_page = None
    last_page = None
    first_visible_item = None
    last_visible_item = None
    list_count = None
    list = []

    def __init__(self, total, page=1, per_page=10, list_count=10, base_uri=None):
        self.total = total
        self.list_count = list_count
        self.page = page
        self.per_page = per_page
        if base_uri:
            self.uri = furl(base_uri)
        else:
            self.uri = furl('')
        self.calculate()

    def calculate(self):
        self.first_page = 1
        self.last_page = int ( ( self.total - 1 ) / self.per_page ) + 1
        self.first_visible_item = (self.page-1) * self.per_page + 1
        self.last_visible_item = self.page * self.per_page
        if self.last_visible_item > self.total:
            self.last_visible_item = self.total

        if not self.list_count % 2:
            self.list_count += 1

        count = self.list_count
        page_list = {}

        page_list[self.page] = True
        count -= 1

        min_list_page = self.page
        max_list_page = self.page

        while count > 0 and ( min_list_page >= self.first_page or max_list_page <= self.last_page ):
            min_list_page -= 1
            max_list_page += 1

            if min_list_page >= self.first_page:
                page_list[min_list_page] = True
                count -= 1

            if max_list_page <= self.last_page:
                page_list[max_list_page] = True
                count -= 1

        self.list = sorted(page_list.keys())

    def limit(self):
        return self.per_page

    def skip(self):
        return (self.page - 1) * self.per_page

    def next(self):
        if ( self.page < self.last_page ):
            return self.page + 1
        return None

    def prev(self):
        if ( self.page > self.first_page ):
            return self.page - 1
        return None
