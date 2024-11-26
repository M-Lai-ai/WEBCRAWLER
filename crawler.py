import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import os
import re
from pathlib import Path
import hashlib
import time
import html2text
import json

class WebCrawler:
    def __init__(self, base_url, output_dir="output"):
        self.base_url = base_url
        self.domain = urlparse(base_url).netloc
        self.urls_by_level = {}  # Pour stocker les URLs par niveau
        self.all_urls = set()    # Pour stocker toutes les URLs
        self.visited_urls = set() # Pour le tracking pendant le crawling
        self.output_dir = output_dir
        self.content_dir = os.path.join(output_dir, "content")
        self.files_dir = os.path.join(output_dir, "files")
        
        # Définir les sous-dossiers pour chaque type de fichier
        self.file_types = {
            'pdf': ['.pdf'],
            'images': ['.png', '.jpg', '.jpeg', '.gif', '.webp'],
            'word': ['.doc', '.docx'],
            'excel': ['.xls', '.xlsx'],
            'csv': ['.csv'],
            'text': ['.txt']
        }
        
        self.html_converter = html2text.HTML2Text()
        self.setup_html_converter()

        # Créer le dossier pour sauvegarder l'état des URLs
        self.urls_dir = os.path.join(output_dir, "urls")
        if not os.path.exists(self.urls_dir):
            os.makedirs(self.urls_dir)

    def save_urls_state(self):
        """Sauvegarde l'état actuel des URLs dans un fichier JSON"""
        state = {
            'urls_by_level': {str(k): list(v) for k, v in self.urls_by_level.items()},
            'all_urls': list(self.all_urls)
        }
        with open(os.path.join(self.urls_dir, 'urls_state.json'), 'w') as f:
            json.dump(state, f, indent=2)

    def load_urls_state(self):
        """Charge l'état des URLs depuis le fichier JSON"""
        try:
            with open(os.path.join(self.urls_dir, 'urls_state.json'), 'r') as f:
                state = json.load(f)
                self.urls_by_level = {int(k): set(v) for k, v in state['urls_by_level'].items()}
                self.all_urls = set(state['all_urls'])
                return True
        except FileNotFoundError:
            return False

    def extract_urls_level(self, level):
        """Extrait les URLs pour un niveau spécifique"""
        if level == 1:
            # Pour le niveau 1, on part de l'URL de base
            current_urls = {self.base_url}
        else:
            # Pour les autres niveaux, on utilise les URLs du niveau précédent
            if level - 1 not in self.urls_by_level:
                print(f"Erreur: Le niveau {level-1} n'a pas encore été crawlé")
                return False
            current_urls = self.urls_by_level[level - 1]

        self.urls_by_level[level] = set()
        
        print(f"\nExtraction des URLs de niveau {level}...")
        for url in current_urls:
            try:
                print(f"Extraction depuis: {url}")
                response = requests.get(url)
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Trouver tous les liens
                for link in soup.find_all('a'):
                    href = link.get('href')
                    if href:
                        full_url = urljoin(url, href)
                        if self.is_valid_url(full_url) and full_url not in self.all_urls:
                            self.urls_by_level[level].add(full_url)
                            self.all_urls.add(full_url)
                
                time.sleep(0.1)  # Petit délai pour ne pas surcharger le serveur
                
            except Exception as e:
                print(f"Erreur lors de l'extraction des URLs de {url}: {e}")

        print(f"\nNiveau {level} terminé. {len(self.urls_by_level[level])} nouvelles URLs trouvées.")
        self.save_urls_state()
        return True

    def show_urls_stats(self):
        """Affiche les statistiques des URLs par niveau"""
        print("\nStatistiques des URLs par niveau :")
        total_urls = 0
        for level in sorted(self.urls_by_level.keys()):
            urls_count = len(self.urls_by_level[level])
            total_urls += urls_count
            print(f"Niveau {level}: {urls_count} URLs")
        print(f"Total: {total_urls} URLs")

    def show_urls_for_level(self, level):
        """Affiche les URLs pour un niveau spécifique"""
        if level in self.urls_by_level:
            print(f"\nURLs de niveau {level}:")
            for url in sorted(self.urls_by_level[level]):
                print(f"- {url}")
        else:
            print(f"Aucune URL trouvée pour le niveau {level}")

    def create_directories(self):
        """Crée tous les dossiers nécessaires"""
        for dir_path in [self.output_dir, self.content_dir, self.files_dir]:
            if not os.path.exists(dir_path):
                os.makedirs(dir_path)
        
        for file_type in self.file_types:
            folder_path = os.path.join(self.files_dir, file_type)
            if not os.path.exists(folder_path):
                os.makedirs(folder_path)

    def setup_html_converter(self):
        """Configure les options de conversion HTML vers Markdown"""
        self.html_converter.ignore_links = False
        self.html_converter.ignore_images = False
        self.html_converter.ignore_emphasis = False
        self.html_converter.ignore_tables = False
        self.html_converter.body_width = 0
        self.html_converter.protect_links = True
        self.html_converter.unicode_snob = True
        self.html_converter.images_to_alt = False
        self.html_converter.default_image_alt = ""

    def is_valid_url(self, url):
        """Vérifie si l'URL appartient au même domaine"""
        return self.domain in url

    def get_file_type_folder(self, extension):
        """Détermine le sous-dossier approprié pour un type de fichier donné"""
        extension = extension.lower()
        for file_type, extensions in self.file_types.items():
            if extension in extensions:
                return file_type
        return None

    def download_file(self, url):
        """Télécharge les fichiers et les place dans les sous-dossiers appropriés"""
        try:
            response = requests.get(url, stream=True)
            if response.status_code == 200:
                extension = os.path.splitext(url)[1].lower()
                file_type = self.get_file_type_folder(extension)
                
                if file_type:
                    file_name = hashlib.md5(url.encode()).hexdigest() + extension
                    file_path = os.path.join(self.files_dir, file_type, file_name)
                    
                    with open(file_path, 'wb') as f:
                        f.write(response.content)
                    
                    return os.path.relpath(file_path, self.content_dir)
                    
        except Exception as e:
            print(f"Erreur lors du téléchargement du fichier {url}: {e}")
        return None

    def clean_content(self, soup):
        """Nettoie le contenu HTML"""
        unwanted_elements = [
            'script', 'style', 'nav', 'header', 'footer', 
            'iframe', 'meta', 'noscript', 'aside', 'form'
        ]
        for element in soup.find_all(unwanted_elements):
            element.decompose()
        
        unwanted_classes = [
            'menu', 'sidebar', 'nav', 'footer', 'header', 
            'comment', 'advertisement', 'social', 'widget'
        ]
        for class_name in unwanted_classes:
            for element in soup.find_all(class_=re.compile(class_name, re.I)):
                element.decompose()
        
        main_content = (
            soup.find('main') or 
            soup.find('article') or 
            soup.find('div', class_='content') or
            soup.find('div', class_='post-content')
        )
        return main_content if main_content else soup.find('body')

    def process_content(self, content, base_url):
        """Traite le contenu HTML et le convertit en Markdown"""
        if not content:
            return ""

        for link in content.find_all('a'):
            href = link.get('href')
            if href:
                full_url = urljoin(base_url, href)
                extension = os.path.splitext(full_url)[1].lower()
                if extension and self.get_file_type_folder(extension):
                    file_path = self.download_file(full_url)
                    if file_path:
                        link['href'] = file_path

        for img in content.find_all('img'):
            src = img.get('src')
            if src:
                full_url = urljoin(base_url, src)
                extension = os.path.splitext(full_url)[1].lower()
                if extension in self.file_types['images']:
                    file_path = self.download_file(full_url)
                    if file_path:
                        img['src'] = file_path

        markdown_content = self.html_converter.handle(str(content))
        markdown_content = re.sub(r'\n\s*\n\s*\n', '\n\n', markdown_content)
        return markdown_content.strip()

    def crawl_all_urls(self):
        """Crawle toutes les URLs collectées"""
        if not self.all_urls:
            print("Aucune URL à crawler. Exécutez d'abord l'extraction des URLs.")
            return

        self.create_directories()
        total_urls = len(self.all_urls)
        processed = 0

        print(f"\nDémarrage du crawling de {total_urls} pages...")
        
        for url in self.all_urls:
            processed += 1
            print(f"\nTraitement de la page {processed}/{total_urls}")
            print(f"Crawling: {url}")
            
            try:
                if url not in self.visited_urls:
                    response = requests.get(url)
                    soup = BeautifulSoup(response.text, 'html.parser')
                    
                    main_content = self.clean_content(soup)
                    if main_content:
                        markdown_content = self.process_content(main_content, url)
                        
                        file_name = hashlib.md5(url.encode()).hexdigest() + '.txt'
                        with open(os.path.join(self.content_dir, file_name), 'w', encoding='utf-8') as f:
                            if soup.title and soup.title.string and soup.title.string.strip():
                                f.write(f"# {soup.title.string.strip()}\n\n")
                            f.write(f"Source: {url}\n\n")
                            f.write("---\n\n")
                            f.write(markdown_content)
                    
                    self.visited_urls.add(url)
                    time.sleep(1)  # Respecter le site
                    
            except Exception as e:
                print(f"Erreur lors du crawling de {url}: {e}")

        # Créer le sitemap
        with open(os.path.join(self.output_dir, 'sitemap.txt'), 'w', encoding='utf-8') as f:
            f.write("# Sitemap\n\n")
            for url in sorted(self.visited_urls):
                f.write(f"- [{url}]({url})\n")

        print(f"\nCrawling terminé. {len(self.visited_urls)} pages traitées.")

