from selenium import webdriver
from selenium.webdriver.chrome.options import Options

options = Options()
options.add_experimental_option("debuggerAddress", "localhost:9222")

driver = webdriver.Chrome(options=options)

print("Título:", driver.title)
print("URL:", driver.current_url)

input("Pressione ENTER para fechar o script...")

driver.quit()