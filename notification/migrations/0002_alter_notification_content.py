# Generated by Django 4.1.3 on 2022-12-13 14:54

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('notification', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='notification',
            name='content',
            field=models.CharField(max_length=255, verbose_name='내용'),
        ),
    ]
