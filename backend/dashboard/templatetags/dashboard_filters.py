from django import template

register = template.Library()


@register.filter
def get_item(dictionary, key):
    return dictionary.get(key, [])


@register.simple_tag
def to_range(start, end):
    return range(start, end + 1)


@register.filter
def dict_get(d, key):
    return d.get(key, "")


@register.filter
def lesson_time(lesson_num, shift):
    times_first = {
        1: "08:00–08:40",
        2: "08:50–09:30",
        3: "09:50–10:30",
        4: "10:50–11:30",
        5: "11:40–12:20",
        6: "12:30–13:10",
        7: "13:20–14:00",
    }
    times_second = {
        8: "13:40–14:20",
        9: "14:40–15:20",
        10: "15:40–16:20",
        11: "16:30–17:10",
        12: "17:20–18:00",
        13: "18:10–18:50",
    }
    try:
        lesson_num = int(lesson_num)
        return times_first[lesson_num] if shift == "1" else times_second[lesson_num]
    except:
        return ""
