# 해야할 일:
# 1. 시정표/시간표 변경 적용
# 시정표 변경 인터페이스: 해당 요일 기본 시간표를 해당 날짜로 복사하는 함수. => 날짜를 입력하면 해당 날짜의 시정표가 준대로 변경.
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render
from django.http import JsonResponse, HttpResponse

def keyboard(request):
	return JsonResponse({
		"type": "buttons",
		"buttons": ["도움말", "바로검색"]
	})

import os
import json
import datetime
import random

from .models import TimeTable, Proposal, Query
from .tools.misc import weekday, weekday_rev, late_night_message, validate_teacher, period_time, format_date

from timetable.settings import BASE_DIR
from shinyang import SHINYANG, this_year, this_semester

from response.forms import ProposalForm


message_no_class_now = "지금은 수업중이 아닙니다.\n<최근 수업>"
message_no_class_today = "오늘은 수업이 없습니다."


def view_class_weekday(grade, division, date):
	assert (grade, division) in SHINYANG[this_year][this_semester]["GRADE_DIVISION"]
	try:
		wd = weekday(date)
		rows = TimeTable.objects.filter(grade=grade, division=division, date=date).order_by("period")
		assert len(rows) > 0
		l = list()
		for i in range(len(rows)):
			l.append("\n{}교시 {} {}".format(rows[i].period, rows[i].subject, rows[i].teacher))
		name = "{}학년 {}반\n{}({}요일):".format(grade, division, format_date(date), wd)
		message = ""
		for r in l:
			message += r
		return JsonResponse({
			"message": {"text": "{}{}".format(name, message)}})
	except:
		return JsonResponse({
			"message": {"text": message_no_class_today}})


def view_teacher_weekday(teacher, date):
	assert validate_teacher(teacher)
	try:
		assert len(TimeTable.objects.filter(teacher__contains=teacher, date=date)) > 0
	except:
		return JsonResponse({
		"message": {"text": "{}\n{} 선생님은 오늘(이날) 수업이 없습니다.".format(format_date(date), teacher)}})
	else:
		wd = weekday(date)
		all_periods = TimeTable.objects.filter(teacher__contains=teacher, date=date).order_by("-period")
		periods = all_periods[0].period
		rows = list()
		for i in range(periods):
			try:
				row = all_periods.get(period=(i+1))
				rows.append("\n{}교시 {} {}-{}".format(i+1, row.subject, row.grade, row.division))
			except:
				rows.append("\n{}교시 -".format(i+1))
		message = ""
		for row in rows:
			message += row
		name = "{}\n{}({}요일):".format(teacher, format_date(date), wd)
		return JsonResponse({
				"message": {"text": ("{}{}").format(name,message)}})


def view_class_now(grade, division, t):
	today = datetime.date.today()
	if today.weekday() >= 5:
		return JsonResponse({
			"message": {"text": "주말에는 지원하지 않는 서비스입니다."}})
	assert (grade, division) in SHINYANG[this_year][this_semester]["GRADE_DIVISION"]
	try:
		if t.time() < datetime.time(9,00):
			message = late_night_message()
			return JsonResponse({
				"message": {"text": message[random.randint(0, len(message)-1)]}})

		row = TimeTable.objects.filter(grade=grade, division=division, date=today, start__lt=t).order_by("-period")[0]
		period = row.period
		name = "{}\n{}학년 {}반({}교시):\n{}".format(format_date(t), grade, division, period, period_time(row))

		if t.time() > row.end:
			message = message_no_class_now
			name = "{}\n{}".format(message, name)
		return JsonResponse({
				"message": {"text": "{}\n{}\n{}".format(name,row.subject,row.teacher)}})
	except:
		return JsonResponse({
				"message": {"text": "{}\n오늘은 수업이 없습니다.".format(format_date(t))}})



def view_teacher_now(teacher, t):
	today = datetime.date.today()
	if today.weekday() >= 5:
		return JsonResponse({
			"message": {"text": "주말에는 지원하지 않는 서비스입니다."}})
	assert validate_teacher(teacher)
	if t.time() < datetime.time(9,00):
		message = late_night_message()
		if t.time() < datetime.time(6,00):
			message.append("집에서 주무시고 계신데 왜요?(꺄아)")
		return JsonResponse({
			"message": {"text": message[random.randint(0, len(message)-1)]}})
	try:
		rows = TimeTable.objects.filter(teacher__contains=teacher, date=today)
		assert len(rows) > 0
	except:
		return JsonResponse({
			"message": {"text": "{}\n{} 선생님은 오늘 수업이 없습니다.".format(format_date(today), teacher)}})
	else:
		# 오늘 수업이 있긴 함
		try:
			row = rows.filter(start__lt=t).order_by("-period")[0]
			name = "{}\n{}({}교시):\n{}".format(format_date(t), row.teacher, row.period, period_time(row))
			teachingDivision = "{}학년 {}반 {}".format(row.grade, row.division, row.subject)

			if t.time() > row.end:
				message = message_no_class_now
				name = "{}\n{}".format(message, name)
			return JsonResponse({
				"message": {"text": "{}\n{}".format(name,teachingDivision)}})
		except:
			period = rows.order_by("period")[0].period
			return JsonResponse({
				"message": {"text": "{}\n오늘 {}선생님의 첫 수업은 {}교시부터입니다.".format(format_date(t), teacher, period)}})


def view_class(target, options):
	now = datetime.datetime.now()
	grade, division = map(int, map(str.strip, target.split("-")))
	try:
		if options["now"]:
			return view_class_now(grade, division, now)
		else:
			return view_class_weekday(grade, division, options["date"])
	except:
		return JsonResponse({
			"message": {"text": "학년과 반이 올바르지 않습니다."}})

def view_teacher(target, options):
	now = datetime.datetime.now()
	try:
		if options["now"]:
			return view_teacher_now(target, now)
		else:
			return view_teacher_weekday(target, options["date"])
	except:
		return JsonResponse({
			"message": {"text": "이름을 다시 한 번 확인하십시오."}})


@csrf_exempt
def answer(request):
	now = datetime.datetime.now()
	today = datetime.date.today()
	try:
		input_request = request.body.decode("utf-8")
		input_json = json.loads(input_request)
		content = input_json["content"].strip()
	except:
		return JsonResponse({
			"message": {"text": "Wrong path. 잘못된 접근입니다."}})
	else:
		if content == "도움말":
			Query.objects.create(option="도움말")
			with open(os.path.join(BASE_DIR, "response/etc/helper.txt")) as f:
				helper = f.read()
			return JsonResponse({
				"message": {"text": helper}})
		elif content == "지금":
			Query.objects.create(option="지금")
			return JsonResponse({
				"message": {"text": "{}년 {}월 {}일 {}시 {}분 {}초".format(now.year, now.month, now.day, now.hour, now.minute, now.second)}})
		elif content == "오늘":
			Query.objects.create(option="오늘")
			return JsonResponse({
				"message": {"text": "{} {}요일".format(today, weekday(today))}})
		elif "검색" in content:
			return JsonResponse({
				"message": {"text": "키보드 작동중"}})
		elif content == "시정표":
			Query.objects.create(option="시정표")
			return view_period_time(today)

		else:
			# determine if an option exists
			try:
				contents = content.split()
				assert len(contents) == 2 and contents[1] in  "지금 오늘 월 화 수 목 금 토 일".split()
				if contents[1] in  ["토", "일"]:
					return JsonResponse({
						"message": {"text": "토, 일요일로는 검색하실 수 없습니다."}})
				target = contents[0]
				if contents[1] == "지금":
					if len(target.split("-")) > 1:
						Query.objects.create(grade_division=target, option="지금")
						return view_class(target, {"now": True})
					else:
						Query.objects.create(teacher=target, option="지금")
						# searching for teacher "now"
						return view_teacher(target, {"now": True})
				# searching for weekday
				else:
					if contents[1] == "오늘":
						wd = today.weekday()
					else:
						wd = weekday_rev(contents[1])
						if today.weekday() > 4:
							today += datetime.timedelta(days=2)
					d = today + datetime.timedelta(days=wd - today.weekday())

					if len(target.split("-")) > 1:
						Query.objects.create(grade_division=target, option=contents[1])
						return view_class(target, {"now": False, "date": d})
					else:
						Query.objects.create(teacher=target, option=contents[1])
						# searching for teacher weekday
						return view_teacher(target, {"now": False, "date": d})

			# there's no option
			except:
				try:
					target = content
					if len(target.split("-")) > 1:
						Query.objects.create(grade_division=target)
						return view_class(target, {"now": False, "date": today})
					else:
						Query.objects.create(teacher=target)
						return view_teacher(target, {"now": False, "date": today})
				except:
					return JsonResponse({"message": {"text": "입력형식이 올바르지 않습니다."}})









def view(request):
	context = {
		"var": "World!",
		"period_list": "1 2 3 4 5 6 7".split(),
		"monday": ["미술","국어","수학","과학","체육","음악","창체"],
		"tuesday": [1,2,3,4,5,6],
		"wednesday": [1,2,3,4,5],
		"thursday": [1,2,3,4,5,6,7],
		"friday": [1,2,3,4,5,6,7],
	}
	return render(request, "response/timetable.html", context)



def proposal(request):
	if request.method == "POST":
		form = ProposalForm(request.POST)
		if form.is_valid():
			cd = form.cleaned_data
			Proposal.objects.create(title=cd["title"], text=cd["text"])
			return render(request, "response/thanks.html")
	else:
		form = ProposalForm()
		return render(request, "response/proposal.html", {"p": form})

def view_period_time(date):
	i = TimeTable.objects.filter(date=date)[0]
	grade, division = i.grade, i.division
	rows = TimeTable.objects.filter(date=date, grade=grade, division=division).order_by("period")
	m = "시정표({}):".format(format_date(date))
	for row in rows:
		m += ('\n{}교시 '.format(row.period) + period_time(row))
	return JsonResponse({"message": {"text": m}})