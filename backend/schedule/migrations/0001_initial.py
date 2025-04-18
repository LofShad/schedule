# Generated by Django 5.1.7 on 2025-04-17 01:43

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='GradeLevel',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('number', models.PositiveSmallIntegerField(unique=True)),
            ],
        ),
        migrations.CreateModel(
            name='Holiday',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateField(unique=True)),
                ('description', models.CharField(blank=True, max_length=200)),
            ],
        ),
        migrations.CreateModel(
            name='Lesson',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('weekday', models.PositiveSmallIntegerField()),
                ('lesson_number', models.PositiveSmallIntegerField()),
            ],
        ),
        migrations.CreateModel(
            name='Room',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, unique=True)),
            ],
        ),
        migrations.CreateModel(
            name='SchoolClass',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('letter', models.CharField(max_length=1)),
                ('shift', models.CharField(choices=[('1', 'Первая'), ('2', 'Вторая')], max_length=1)),
            ],
        ),
        migrations.CreateModel(
            name='StudyPlan',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=50, unique=True)),
            ],
        ),
        migrations.CreateModel(
            name='StudyPlanEntry',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('hours_per_week', models.PositiveSmallIntegerField()),
            ],
        ),
        migrations.CreateModel(
            name='Subject',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, unique=True)),
                ('subject_area', models.CharField(choices=[('language', 'Русский язык и литература'), ('foreign', 'Иностранные языки'), ('math', 'Математика и информатика'), ('social', 'Общественно-научные предметы'), ('natural', 'Естественнонаучные предметы'), ('culture', 'Духовно-нравственная культура'), ('art', 'Искусство'), ('tech', 'Технология'), ('sport', 'Физическая культура и ОБЖ'), ('other', 'Другое')], max_length=50)),
                ('difficulty', models.CharField(choices=[('easy', 'Лёгкая'), ('medium', 'Средняя'), ('hard', 'Высокая')], default='medium', max_length=10)),
            ],
        ),
        migrations.CreateModel(
            name='SubjectHours',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('hours_per_week', models.PositiveSmallIntegerField()),
            ],
        ),
    ]
