import os
import discord
import logging
import pandas as pd
import json

# discord user token
token = "___________________________________________________________"

logging.basicConfig(level=logging.INFO)

client = discord.Client()
guild = discord.Guild

@client.event
async def on_ready():
    print('We have logged in as {0.user}'.format(client))

    target_list = {}
    target_ch_id = __________________
    channel = client.get_channel(target_ch_id)
    last_message = None
    limit = 100

    f = open('./theme.list', 'w', encoding='utf-8')

    while True:
        if last_message is None:
            messages = await channel.history(oldest_first=True, limit=limit).flatten()
        else:
            messages = await channel.history(oldest_first=True, limit=limit, after=last_message).flatten()
        
        if len(messages) == 0:
            break

        for message in messages:
            last_message = message
            title = message.content
            files = []
    
            for attachment in message.attachments:
                filename = attachment.filename
                url = attachment.url
                files.append({'filename':filename, 'url':url})
            
            if title in target_list.keys():
                att_list = target_list[title]
                att_list += files
            else:
                target_list[title] = files

            print(title)
            print(target_list[title])

    f.write(json.dumps(target_list, indent=4, ensure_ascii=False))
    print('file write completed')
    f.close()

client.run(token, bot=False)

