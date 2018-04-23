import os
import bmemcached    
import praw


username = os.environ['REDDIT_USERNAME']
password = os.environ['REDDIT_PASSWORD']

login_info = [username, password]

def main():
    mc = bmemcached.Client(
        os.environ.get('MEMCACHEDCLOUD_SERVERS').split(','),
        os.environ.get('MEMCACHEDCLOUD_USERNAME'),
        os.environ.get('MEMCACHEDCLOUD_PASSWORD'))
        
    obj = mc.get(input_key)
        
    if not obj:
        return False
    else:
        return True

    mc.set(input_key, "True")

    mc.delete(key)


main()
