import time
import asyncio
import json
import re
from telethon import TelegramClient
from telethon.errors import PhoneNumberInvalidError, ApiIdInvalidError, SessionPasswordNeededError

class TelegramForwarder:
    def __init__(self, api_id, api_hash, phone_number):
        self.api_id = api_id
        self.api_hash = api_hash
        self.phone_number = phone_number
        self.client = None
        self.replacement_dict = {}

    async def connect(self):
        if self.client:
            await self.client.disconnect()
            await self.client.disconnected
        
        self.client = TelegramClient('session_' + self.phone_number, self.api_id, self.api_hash)
        
        try:
            await self.client.connect()
            if not await self.client.is_user_authorized():
                await self.client.send_code_request(self.phone_number)
                code = input('Enter the code: ')
                try:
                    await self.client.sign_in(self.phone_number, code)
                except SessionPasswordNeededError:
                    password = input('Two step verification is enabled. Please enter your password: ')
                    await self.client.sign_in(password=password)
            print("Successfully connected and authorized!")
        except Exception as e:
            print(f"Error during connection: {str(e)}")
            raise

    async def list_chats(self):
        await self.connect()

        dialogs = await self.client.get_dialogs()
        chats = []
        with open(f"chats_of_{self.phone_number}.txt", "w", encoding='utf-8') as chats_file:
            for index, dialog in enumerate(dialogs, start=1):
                chat_info = f"Index: {index}, Chat ID: {dialog.id}, Title: {dialog.title}"
                print(chat_info)
                chats_file.write(chat_info + "\n")
                chats.append({"index": index, "id": dialog.id, "title": dialog.title})

        print("List of groups printed successfully!")
        return chats

    def replace_text(self, text):
        if text is None:
            return None
        
        for old_word, new_word in self.replacement_dict.items():
            pattern = re.compile(re.escape(old_word), re.IGNORECASE)
            text = pattern.sub(new_word, text)
        
        return text

    async def forward_messages_to_channel(self, source_chat_id, destination_channel_id, keywords):
        await self.connect()
        
        source_chat = await self.client.get_entity(source_chat_id)
        destination_chat = await self.client.get_entity(destination_channel_id)
        
        print(f"Forwarding messages from '{source_chat.title}' ({source_chat_id}) to '{destination_chat.title}' ({destination_channel_id})")

        last_message_id = (await self.client.get_messages(source_chat_id, limit=1))[0].id

        self.save_last_used_chats(source_chat_id, destination_channel_id)

        while True:
            print("Checking for messages and forwarding them...")
            messages = await self.client.get_messages(source_chat_id, min_id=last_message_id, limit=None)

            for message in reversed(messages):
                if message.text:
                    if keywords and any(keyword.lower() in message.text.lower() for keyword in keywords):
                        print(f"Message contains a keyword: {message.text}")
                        replaced_text = self.replace_text(message.text)
                        if replaced_text:
                            await self.client.send_message(destination_channel_id, replaced_text)
                            print("Message forwarded")
                        else:
                            print("Message not forwarded: Text was empty after replacement")
                    elif not keywords:
                        replaced_text = self.replace_text(message.text)
                        if replaced_text:
                            await self.client.send_message(destination_channel_id, replaced_text)
                            print("Message forwarded")
                        else:
                            print("Message not forwarded: Text was empty after replacement")
                else:
                    print("Message not forwarded: No text content")

                last_message_id = max(last_message_id, message.id)

            await asyncio.sleep(5)

    async def forward_last_messages(self):
        await self.connect()
        
        last_used_chats = self.load_last_used_chats()
        if not last_used_chats:
            print("No previous forwarding session found.")
            return

        source_chat_id = last_used_chats["source"]
        destination_channel_id = last_used_chats["destination"]

        source_chat = await self.client.get_entity(source_chat_id)
        destination_chat = await self.client.get_entity(destination_channel_id)

        print(f"Forwarding messages from '{source_chat.title}' ({source_chat_id}) to '{destination_chat.title}' ({destination_channel_id})")

        keywords = input("Enter keywords (comma separated if multiple, or leave blank): ").split(",")
        await self.forward_messages_to_channel(source_chat_id, destination_channel_id, keywords)

    def save_last_used_chats(self, source_chat_id, destination_channel_id):
        with open("last_used_chats.txt", "w") as f:
            f.write(f"{source_chat_id}\n{destination_channel_id}")

    def load_last_used_chats(self):
        try:
            with open("last_used_chats.txt", "r") as f:
                lines = f.readlines()
                return {
                    "source": int(lines[0].strip()),
                    "destination": int(lines[1].strip())
                }
        except FileNotFoundError:
            return {}

    def add_replacement_word(self):
        old_word = input("Enter the word to be replaced: ")
        new_word = input("Enter the replacement word: ")
        self.replacement_dict[old_word.lower()] = new_word
        self.save_replacement_dict()
        print(f"Replacement added: '{old_word}' -> '{new_word}'")

    def remove_replacement_word(self):
        old_word = input("Enter the word to remove from replacements: ")
        if old_word.lower() in self.replacement_dict:
            del self.replacement_dict[old_word.lower()]
            self.save_replacement_dict()
            print(f"Replacement for '{old_word}' removed.")
        else:
            print(f"'{old_word}' not found in replacements.")

    def list_replacement_words(self):
        if not self.replacement_dict:
            print("No replacement words set.")
        else:
            print("Current replacement words:")
            for old_word, new_word in self.replacement_dict.items():
                print(f"'{old_word}' -> '{new_word}'")

    def save_replacement_dict(self):
        with open("replacement_words.json", "w") as f:
            json.dump(self.replacement_dict, f)

    def load_replacement_dict(self):
        try:
            with open("replacement_words.json", "r") as f:
                self.replacement_dict = json.load(f)
        except FileNotFoundError:
            self.replacement_dict = {}

def read_credentials():
    try:
        with open("credentials.txt", "r") as file:
            lines = file.readlines()
            api_id = lines[0].strip()
            api_hash = lines[1].strip()
            phone_number = lines[2].strip()
            return api_id, api_hash, phone_number
    except FileNotFoundError:
        print("Credentials file not found.")
        return None, None, None

def write_credentials(api_id, api_hash, phone_number):
    with open("credentials.txt", "w") as file:
        file.write(f"{api_id}\n")
        file.write(f"{api_hash}\n")
        file.write(f"{phone_number}\n")

def format_phone_number(phone):
    digits = re.sub(r'\D', '', phone)
    
    if not digits.startswith('380'):
        digits = '380' + digits
    
    formatted = f"+{digits[:3]} {digits[3:5]} {digits[5:8]} {digits[8:10]} {digits[10:]}"
    return formatted.strip()

async def change_api():
    while True:
        api_id = input("Enter your API ID: ")
        api_hash = input("Enter your API Hash: ")
        phone_number = input("Enter your phone number: ")

        formatted_phone = format_phone_number(phone_number)

        print(f"\nConfirm your details:")
        print(f"API ID: {api_id}")
        print(f"API Hash: {api_hash}")
        print(f"Phone Number: {formatted_phone}")

        confirm = input("\nIs this correct? (y/n): ").lower()
        if confirm == 'y':
            write_credentials(api_id, api_hash, formatted_phone)
            return api_id, api_hash, formatted_phone
        else:
            print("Let's try again.\n")

async def settings_menu(forwarder):
    while True:
        print("\nSettings Menu:")
        print("1. Change API")
        print("2. Manage Text Replacements")
        print("3. Return to Main Menu")

        choice = input("Enter your choice: ")

        if choice == "1":
            api_id, api_hash, phone_number = await change_api()
            forwarder.__init__(api_id, api_hash, phone_number)
            await forwarder.connect()
            print("API credentials updated successfully.")
        elif choice == "2":
            await manage_replacements(forwarder)
        elif choice == "3":
            break
        else:
            print("Invalid choice")

async def manage_replacements(forwarder):
    while True:
        print("\nManage Text Replacements:")
        print("1. Add Replacement")
        print("2. Remove Replacement")
        print("3. List Replacements")
        print("4. Return to Settings Menu")

        choice = input("Enter your choice: ")

        if choice == "1":
            forwarder.add_replacement_word()
        elif choice == "2":
            forwarder.remove_replacement_word()
        elif choice == "3":
            forwarder.list_replacement_words()
        elif choice == "4":
            break
        else:
            print("Invalid choice")

async def main():
    api_id, api_hash, phone_number = read_credentials()

    if api_id is None or api_hash is None or phone_number is None:
        api_id, api_hash, phone_number = await change_api()

    forwarder = TelegramForwarder(api_id, api_hash, phone_number)
    forwarder.load_replacement_dict()

    while True:
        print("\nMain Menu:")
        print("1. List Chats")
        print("2. Forward Messages")
        print("3. Forward Last Messages")
        print("4. Settings")
        print("5. Exit")

        choice = input("Enter your choice: ")

        try:
            if choice == "1":
                chats = await forwarder.list_chats()
            elif choice == "2":
                if 'chats' not in locals():
                    chats = await forwarder.list_chats()
                source_chat_index = int(input("Enter the source chat index: "))
                destination_chat_index = int(input("Enter the destination chat index: "))
                keywords = input("Enter keywords (comma separated if multiple, or leave blank): ").split(",")
                source_chat_id = chats[source_chat_index - 1]["id"]
                destination_channel_id = chats[destination_chat_index - 1]["id"]
                await forwarder.forward_messages_to_channel(source_chat_id, destination_channel_id, keywords)
            elif choice == "3":
                await forwarder.forward_last_messages()
            elif choice == "4":
                await settings_menu(forwarder)
            elif choice == "5":
                print("Exiting the program.")
                break
            else:
                print("Invalid choice")
        except Exception as e:
            print(f"An error occurred: {str(e)}")
            print("Please try again.")

if __name__ == "__main__":
    asyncio.run(main())
