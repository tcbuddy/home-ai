import logging
import os
import sys
from time import sleep

from flask import Flask
from kik import KikApi
from kik.messages import SuggestedResponseKeyboard, TextResponse

import config
from bot.kik_bot import KikBotOutput
from scripts.calendar import CalendarScript
from scripts.current_time import CurrentTimeScript
from scripts.exit_process import ExitProcessScript
from scripts.get_tunnel_url import GetTunnelURLScript
from scripts.headlines import HeadlinesScript, HeadlinesLinksScript
from scripts.quote_of_the_day import QuoteOfTheDayScript
from scripts.take_picture import TakePictureScript
from scripts.weather import WeatherScript
from utils.command import AnyCommand, TextCommand
from utils.output import MultiOutput, ThreadedOutput
from utils.response import Response, ResponseSet
from utils.script import CompositeScript, EchoScript, EchoTextScript, StaticTextScript, ParallelScript
from utils.sound import play_mp3, pair_speaker
from workers.alarm_clock import get_worker as generate_alarm_worker
from workers.ngrok import get_worker as generate_ngrok_worker
from workers.speech import SpeechOutput
from workers.voice import VoiceProcessor
from workers.web_server import get_worker as generate_web_worker

logging.getLogger().setLevel(logging.DEBUG)

# Check if super user (if yes, GTFO)
if os.geteuid() == 0:
    logging.error('This is not meant to be run as root')
    sys.exit(1)

# Outputs
kik = KikApi(config.KIK_BOT_USERNAME, config.KIK_BOT_API_KEY)
bot_output = KikBotOutput(kik=kik, default_keyboard=SuggestedResponseKeyboard(
    responses=[
        TextResponse('Check Running'),
        TextResponse('Tunnel URL'),
        TextResponse('Alarm Clock'),
        TextResponse('Picture'),
        TextResponse('Quote'),
        TextResponse('Headlines'),
        TextResponse('Weather'),
        TextResponse('Calendar'),
        TextResponse('Kill'),
        TextResponse('Restart')
    ]
))

speech_output = SpeechOutput(speaker_mac_address=config.SPEAKER_MAC_ADDRESS,
                             sink_name=config.SINK_NAME)

static_folder = '{}/{}'.format(os.path.dirname(os.path.abspath(__file__)), 'static')
web_app = Flask(__name__, static_folder=static_folder)

bot_and_speech_output = MultiOutput(outputs=[
    ThreadedOutput(output=speech_output),
    bot_output
])

# Scripts
calendar_script = CalendarScript()
headlines_script = HeadlinesScript()
headlines_links_script = HeadlinesLinksScript()
weather_script = WeatherScript()
quote_script = QuoteOfTheDayScript()
current_time_script = CurrentTimeScript()
good_morning_script = CompositeScript(scripts=[
    StaticTextScript(body='Good morning Remi. Time to wake up'),
    current_time_script,
    calendar_script,
    headlines_script,
    weather_script,
    quote_script,
    StaticTextScript(body='Have an amazing day')
])
take_picture_script = TakePictureScript(static_folder=static_folder)
get_tunnel_url_script = GetTunnelURLScript()
running_script = StaticTextScript(body='I am running indeed')

# Responders
bot_response = ResponseSet(responses=[
    Response(
        label='Check running',
        command=TextCommand(keywords=['check']),
        script=running_script.outputting_to(bot_and_speech_output)
    ),
    Response(
        label='Alarm',
        command=TextCommand(keywords=['alarm', 'clock', 'morning']),
        script=ParallelScript(scripts=[
            good_morning_script.outputting_to(speech_output),
            headlines_links_script.outputting_to(bot_output)
        ])
    ),
    Response(
        label='Picture',
        command=TextCommand(keywords=['picture']),
        script=take_picture_script.outputting_to(bot_output)
    ),
    Response(
        label='Quote',
        command=TextCommand(keywords=['quote']),
        script=quote_script.outputting_to(bot_and_speech_output)
    ),
    Response(
        label='Calendar',
        command=TextCommand(keywords=['calendar', 'events']),
        script=calendar_script.outputting_to(bot_and_speech_output)
    ),
    Response(
        label='Weather',
        command=TextCommand(keywords=['weather']),
        script=weather_script.outputting_to(bot_and_speech_output)
    ),
    Response(
        label='Headlines',
        command=TextCommand(keywords=['headlines', 'news']),
        script=ParallelScript(scripts=[
            headlines_script.outputting_to(speech_output),
            headlines_links_script.outputting_to(bot_output)
        ])
    ),
    Response(
        label='Tunnel URL',
        command=TextCommand(keywords=['tunnel']),
        script=get_tunnel_url_script.outputting_to(bot_output)
    ),
    Response(
        label='Kill',
        command=TextCommand(keywords=['kill']),
        script=ExitProcessScript(exit_code=0).outputting_to(bot_output)
    ),
    Response(
        label='Restart',
        command=TextCommand(keywords=['restart', 'reboot']),
        script=ExitProcessScript(exit_code=1).outputting_to(bot_output)
    )
], default_script=ParallelScript(scripts=[
    StaticTextScript(body='Unrecognized command, playing on speaker').outputting_to(bot_output),
    EchoScript().outputting_to(speech_output)
]), confused_script=StaticTextScript(body='I am confused').outputting_to(bot_output))

voice_response = ResponseSet(responses=[
    Response(
        label='Alarm',
        command=TextCommand(keywords=['alarm', 'clock', 'morning']),
        script=good_morning_script.outputting_to(speech_output)
    ),
    Response(
        label='Picture',
        command=TextCommand(keywords=['picture']),
        script=take_picture_script.outputting_to(bot_output)
    ),
    Response(
        label='Quote',
        command=TextCommand(keywords=['quote']),
        script=quote_script.outputting_to(bot_and_speech_output)
    ),
    Response(
        label='Calendar',
        command=TextCommand(keywords=['calendar', 'events']),
        script=calendar_script.outputting_to(bot_and_speech_output)
    ),
    Response(
        label='Weather',
        command=TextCommand(keywords=['weather']),
        script=weather_script.outputting_to(bot_and_speech_output)
    ),
    Response(
        label='Headlines',
        command=TextCommand(keywords=['headlines', 'news']),
        script=ParallelScript(scripts=[
            headlines_script.outputting_to(speech_output),
            headlines_links_script.outputting_to(bot_output)
        ])
    ),
], confused_script=ParallelScript(scripts=[
    EchoTextScript(echo_format='I am confused (input: {})').outputting_to(bot_output),
    StaticTextScript(body='I am confused').outputting_to(speech_output)
]))

alarm_response = Response(
    label='Alarm',
    command=AnyCommand(),
    script=ParallelScript(scripts=[
        good_morning_script.outputting_to(speech_output),
        headlines_links_script.outputting_to(bot_output)
    ])
)

# Workers
logging.debug('Starting threads')


def resume_with_delay():
    sleep(1)  # wait a second before resuming processing to avoid processing delayed speeches
    voice_processor.resume_processing()


voice_processor = VoiceProcessor(prefix='please', response=voice_response)
speech_output.start_speech_callback = voice_processor.pause_processing
speech_output.end_speech_callback = resume_with_delay

threads = [
    generate_web_worker(web_app=web_app, port=config.KIK_BOT_PORT, kik=kik,
                        response_set=bot_response,
                        recipient_username=config.KIK_BOT_RECIPIENT_USERNAME),
    generate_ngrok_worker(port=config.KIK_BOT_PORT, kik=kik),
    generate_alarm_worker(response=alarm_response),
    speech_output.get_worker(),
    voice_processor.processing_worker()
]

for thread in threads:
    thread.start()

logging.debug('All threads started')

# Starting voice input process
voice_processor.input_worker().start()

pair_speaker(mac_address=config.SPEAKER_MAC_ADDRESS, sink_name=config.SINK_NAME)
play_mp3('assets/initialized-home-ai.mp3')

for thread in threads:
    thread.join()
