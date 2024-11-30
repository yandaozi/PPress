class Pagination:
    """通用分页类"""
    def __init__(self, items, total, page, per_page, total_pages):
        self.items = items
        self.total = total
        self.page = page
        self.per_page = per_page
        self.pages = total_pages
        
    @property
    def has_prev(self):
        return self.page > 1
        
    @property
    def has_next(self):
        return self.page < self.pages
        
    @property
    def prev_num(self):
        return self.page - 1 if self.has_prev else None
        
    @property
    def next_num(self):
        return self.page + 1 if self.has_next else None
    
    def iter_pages(self, left_edge=2, left_current=2, right_current=5, right_edge=2):
        last = 0
        for num in range(1, self.pages + 1):
            if (num <= left_edge or
                (num > self.page - left_current - 1 and
                 num < self.page + right_current) or
                num > self.pages - right_edge):
                if last + 1 != num:
                    yield None
                yield num
                last = num

    @classmethod
    def create_pagination(cls, query, page, per_page):
        """从查询创建分页对象"""
        total = query.count()
        total_pages = (total + per_page - 1) // per_page
        page = min(max(page, 1), total_pages if total_pages > 0 else 1)
        items = query.offset((page - 1) * per_page).limit(per_page).all()
        
        return cls(
            items=items,
            total=total,
            page=page,
            per_page=per_page,
            total_pages=total_pages
        ) 