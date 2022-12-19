# Generated by Django 4.1.3 on 2022-12-19 12:45

from django.conf import settings
import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Place',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('place_name', models.CharField(max_length=50, verbose_name='장소명')),
                ('category', models.CharField(max_length=20, verbose_name='카테고리')),
                ('rating', models.DecimalField(decimal_places=2, default=0, max_digits=3, validators=[django.core.validators.MaxValueValidator(5)], verbose_name='별점')),
                ('menu', models.TextField(null=True, verbose_name='메뉴')),
                ('place_desc', models.CharField(max_length=255, null=True, verbose_name='소개글')),
                ('place_address', models.CharField(max_length=100, verbose_name='주소')),
                ('place_number', models.CharField(max_length=20, verbose_name='장소 전화번호')),
                ('place_time', models.CharField(max_length=30, verbose_name='영업 시간')),
                ('place_img', models.TextField(null=True, verbose_name='장소 이미지')),
                ('latitude', models.CharField(max_length=50, null=True, verbose_name='위도')),
                ('longitude', models.CharField(max_length=50, null=True, verbose_name='경도')),
                ('hit', models.PositiveIntegerField(default=0, verbose_name='조회수')),
                ('place_bookmark', models.ManyToManyField(blank=True, related_name='bookmark_place', to=settings.AUTH_USER_MODEL, verbose_name='장소 북마크')),
            ],
            options={
                'db_table': 'places',
            },
        ),
    ]
