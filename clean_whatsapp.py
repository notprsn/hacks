import re
import os

def process_messages(input_file, output_file):
    # Check if input file exists
    if not os.path.exists(input_file):
        print(f"Error: {input_file} not found.")
        return

    with open(input_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    messages = []
    current_message = []
    
    # Regex to match the timestamp and sender pattern
    # Looking for: [DD/MM/YYYY, HH:MM:SS] Sender Name: Message Content
    # We use a non-greedy match for the sender name part ".*?:"
    pattern = re.compile(r'^\[\d{2}/\d{2}/\d{4}, \d{2}:\d{2}:\d{2}\] .*?: (.*)')

    for line in lines:
        match = pattern.match(line)
        if match:
            # If we have collected a previous message, add it to the list
            if current_message:
                # Join lines and strip leading/trailing whitespace from the message
                messages.append("".join(current_message).strip())
                current_message = []
            
            # Extract the message content from the line (removing timestamp and sender)
            # match.group(1) is the content part. We append a newline to maintain structure.
            first_line_content = match.group(1)
            current_message.append(first_line_content + "\n")
        else:
            # This is a continuation of the previous message (or empty lines between messages)
            current_message.append(line)

    # Don't forget to add the very last message found
    if current_message:
        messages.append("".join(current_message).strip())

    # Write the processed messages to the output file
    with open(output_file, 'w', encoding='utf-8') as f:
        # Separator as requested
        separator = "\n\n----\n\n"
        f.write(separator.join(messages))
        # Ensure a final newline at the end of the file
        f.write("\n")

    print(f"Successfully processed {len(messages)} messages.")
    print(f"Output saved to {output_file}")

if __name__ == "__main__":
    # Assuming the input file is named msgs.txt as seen in the directory
    # and we want to output to cleaned_msgs.txt
    process_messages('msgs.txt', 'cleaned_msgs.txt')
