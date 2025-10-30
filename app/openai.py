# deepgram troubleshooting
# @app.post('/synthetic_voices')
# async def handle_tts_request(request: Request, flow: str = Query(...)):
#     '''route handler for Deepgram synthesized speech'''
#     headers = {
#         "Content-Type": "application/json",
#         "Authorization": f"Bearer {OPENAI_API_KEY}"
#     }
#     data = await request.json()
#     text = data.get('text')
#     payload = {
#         "model":  "tts-1",
#         "input":  text,
#         "voice":  "alloy"
#     }
#
#     if not text:
#         logger.error("No text provided in the request")
#         raise HTTPException(status_code=400, detail='no text provided')
#
#     logger.info("Sending request to Deepgram API")
#     try:
#         async with httpx.AsyncClient() as client:
#             response = await client.post(OPENAI_API_URL, headers=headers, json=payload)
#             if response.status_code != 200:
#                 logger.error(f'failed to communicate with Deepgram API with text request, {response.text}')
#                 raise HTTPException(status_code=response.status_code, detail=response.text)
#         content_length = response.headers.get('Content-Length')
#         if content_length and int(content_length) != len(response.content):
#             logger.error("Incomplete file received from Deepgram API")
#             raise HTTPException(status_code=500, detail='Incomplete file received from Deepgram API')
#
#         flow_name = quote(flow)
#         formatted_now = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
#         flow_filename = f"{formatted_now}_{flow_name}.mp3"
#         # with open (flow_filename, 'wb') as f:
#         #     f.write(response.content)
#         # print(f'File saved to {flow_filename}')
#         # using aiofiles for async file ops
#         async with aiofiles.open(flow_filename, 'wb') as f:
#             await f.write(response.content)
#             await f.flush()
#         logger.info(f'file saved to {flow_filename}')
#
#         await assets.uploadFiles([flow_filename], 'audio_files')
#         #file_link = await assets.generateLink(f'audio_files/20240709_141802_existing_patient.mp3', '15m')
#         file_link = await assets.generateLink(f'audio_files/{flow_filename}', '15m')
#         logger.info(f"MP3 file successfully uploaded: {file_link}")
#     except Exception as e:
#         logger.exception("An error occured during the last step of uploading the file to VCR")
#         raise HTTPException(status_code=500, detail=str(e))
#
#
#     return JSONResponse(content={'status': 'success', 'url': file_link, 'flow_filename': flow_filename}, status_code=200)
#
