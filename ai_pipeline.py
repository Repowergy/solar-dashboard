#!/usr/bin/env python3
# Solar Product AI Pipeline - Multi-Modal Product Recognition
# ============================================================

import pandas as pd
import requests
import re
import json
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

# ============================================
# 1. DATA CLASSES
# ============================================

@dataclass
class ProductAnalysis:
    original_title: str
    detected_category: str
    confidence_category: float
    extracted_brand: str
    extracted_model: str
    extracted_power_kw: float
    extracted_specs: Dict[str, str]
    has_defects: bool
    image_description: str
    similar_products: List[str]
    data_quality_score: float
    suggested_fixes: List[str]

# ============================================
# 2. CONFIGURATION
# ============================================

SOLAR_CATEGORIES = {
    'Wechselrichter': ['inverter', 'wechselrichter', 'mppt', 'wechselrichter', 'inverter', 'micro inverter'],
    'Solarmodul': ['solar', 'pv', 'panel', 'modul', 'module', 'shingled', 'bifacial', 'mono', 'poly'],
    'Speicher': ['battery', 'batterie', 'speicher', 'akku', 'ess', 'lithium', 'storage'],
    'Kabel': ['cable', 'kabel', 'leitung', 'wire', 'h1z2z2', 'dc cable'],
    'Montage': ['mount', 'halter', 'befestigung', 'rack', 'montage', 'mounting'],
    'Stecker': ['connector', 'stecker', 'anschluss', 'mc4', 'plug', 'adapter'],
    'Optimizer': ['optimizer', 'power optimizer', 'tigo', 'solaredge'],
    'Monitoring': ['monitor', 'meter', 'sensor', 'logger', 'display']
}

BRAND_PATTERNS = {
    'Deye': r'\b(Deye|DEYE)\b',
    'Huawei': r'\b(Huawei|HUAWEI)\b',
    'Fronius': r'\b(Fronius|FRONIUS)\b',
    'SMA': r'\b(SMA|sma)\b',
    'SolarEdge': r'\b(SolarEdge|solaredge|SE-)\b',
    'KBE': r'\b(KBE|kbe|KBE SOLAR)\b',
    'LONGi': r'\b(LONGi|longi|LONG-i)\b',
    'JA Solar': r'\b(JA Solar|JASolar|JA-Solar)\b',
    'Trina': r'\b(Trina|TRINA|TrinaSolar)\b',
    'Jinko': r'\b(Jinko|JINKO|JinkoSolar)\b',
    'Canadian Solar': r'\b(Canadian|CanadianSolar|CS)\b',
    'Qcells': r'\b(Qcells|QCELLS|Q-Cells)\b',
    'AIKO': r'\b(AIKO|aiko)\b',
    'Victron': r'\b(Victron|VICTRON)\b',
    'Fimer': r'\b(Fimer|FIMER)\b',
    'ABB': r'\b(ABB|abb)\b'
}

POWER_PATTERNS = [
    (r'(\b[\n]*[\n]*[\n]*[\n]*[\n]*[\n]*[\n]*[\n]*[\n]*[\n]*[\n]*[\n]*[\n]*[\n]*[\n]*[\n]*)', 'single'),
    (r'(\b[\n]*[\n]*[\n]*[\n]*[\n]*[\n]*[\n]*[\n]*[\n]*[\n]*)', 'single'),
]

# ============================================
# 3. TEXT-BASED KI ANALYSIS
# ============================================

class TextKIAnalyzer:
    def __init__(self):
        self.categories = SOLAR_CATEGORIES
        self.brands = BRAND_PATTERNS
        self.power_patterns = POWER_PATTERNS
    
    def analyze(self, row: pd.Series) -> dict:
        title = str(row.get('product_title', ''))
        category = str(row.get('category', ''))
        description = str(row.get('description', ''))
        combined_text = (title + ' ' + category + ' ' + description).lower()
        
        result = {
            'detected_category': self._detect_category(combined_text),
            'confidence_category': self._get_category_confidence(combined_text),
            'extracted_brand': self._extract_brand(title, row),
            'extracted_model': self._extract_model(title),
            'extracted_power_kw': self._extract_power(title),
            'extracted_specs': self._extract_specs(title, description),
            'suggested_fixes': self._generate_fixes(row)
        }
        
        return result
    
    def _detect_category(self, text: str) -> Tuple[str, float]:
        scores = {}
        for category, keywords in self.categories.items():
            score = sum(1 for kw in keywords if kw in text)
            if score > 0:
                scores[category] = score / len(keywords) * 100
        
        if scores:
            best_cat = max(scores, key=scores.get)
            return best_cat, scores[best_cat]
        return 'Sonstiges', 50.0
    
    def _get_category_confidence(self, text: str) -> float:
        matches = sum(1 for cats in self.categories.values() for kw in cats if kw in text)
        return min(100, matches * 20)
    
    def _extract_brand(self, title: str, row: pd.Series) -> str:
        # First check explicit fields
        if pd.notna(row.get('brand')) and str(row['brand']).strip():
            return str(row['brand']).strip()
        if pd.notna(row.get('manufacturer')) and str(row['manufacturer']).strip():
            return str(row['manufacturer']).strip()
        
        # Then scan title
        title_upper = title.upper()
        for brand, pattern in self.brands.items():
            if re.search(pattern, title_upper, re.IGNORECASE):
                return brand
        
        return 'Unbekannt'
    
    def _extract_model(self, title: str) -> str:
        # Common model patterns: SUN-10K-G04, MIN-3000H, etc.
        patterns = [
            r'([A-Z]+-[\n]*[\n]*[\n]*[\n]*[\n]*[\n]*[\n]*[\n]*[\n]*[\n]*)',
            r'([A-Z]{2,}[\n]*[\n]*[\n]*[\n]*[\n]*[\n]*[\n]*)',
            r'(MIN[-\n]*[\n]*[\n]*[\n]*[\n]*[\n]*)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, title, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        return ''
    
    def _extract_power(self, title: str) -> Optional[float]:
        for pattern, _ in self.power_patterns:
            match = re.search(pattern, title, re.IGNORECASE)
            if match:
                try:
                    power_str = match.group(1).replace(',', '.').strip()
                    return float(power_str)
                except:
                    pass
        return None
    
    def _extract_specs(self, title: str, description: str) -> Dict[str, str]:
        specs = {}
        
        # Extract voltage
        voltage_match = re.search(r'(\b[\n]*[\n]*[\n]*[\n]*[\n]*[\n]*[\n]*[\n]*[\n]*[\n]*)', title + description)
        if voltage_match:
            specs['voltage'] = voltage_match.group(1)
        
        # Extract cable size
        size_match = re.search(r'(\b[\n]*[\n]*[\n]*[\n]*[\n]*[\n]*[\n]*[\n]*[\n]*[\n]*)', title)
        if size_match:
            specs['cable_size'] = size_match.group(1)
        
        # Extract length
        length_match = re.search(r'(\b[\n]*[\n]*[\n]*[\n]*[\n]*[\n]*[\n]*[\n]*[\n]*[\n]*)', title)
        if length_match:
            specs['length'] = length_match.group(1)
        
        return specs
    
    def _generate_fixes(self, row: pd.Series) -> List[str]:
        fixes = []
        
        if pd.isna(row.get('brand')) and pd.isna(row.get('manufacturer')):
            fixes.append('Marke aus Titel extrahieren')
        
        if pd.isna(row.get('description')) or len(str(row.get('description', ''))) < 50:
            fixes.append('Beschreibung hinzufügen')
        
        if pd.isna(row.get('image_urls')):
            fixes.append('Produktbild beschaffen')
        
        if pd.isna(row.get('price')):
            fixes.append('Preis ergänzen')
        
        return fixes

# ============================================
# 4. IMAGE-BASED KI ANALYSIS (Vision API)
# ============================================

class ImageKIAnalyzer:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.mock_mode = api_key is None
    
    def analyze_image(self, image_url: str) -> dict:
        if self.mock_mode:
            return self._mock_image_analysis(image_url)
        
        # Real implementation with OpenAI/Gemini/Vision API
        # This would call the actual API
        return self._mock_image_analysis(image_url)
    
    def _mock_image_analysis(self, image_url: str) -> dict:
        # Simulated AI analysis
        return {
            'has_product': True,
            'image_type': self._detect_image_type(image_url),
            'dominant_color': 'silver/white',
            'has_logo': self._has_brand_logo(image_url),
            'quality_score': 85,
            'description': 'Solar panel or inverter product image',
            'detected_defects': []
        }
    
    def _detect_image_type(self, url: str) -> str:
        url_lower = url.lower()
        if 'inverter' in url_lower or 'mppt' in url_lower:
            return 'inverter'
        elif 'solar' in url_lower or 'panel' in url_lower or 'module' in url_lower:
            return 'solar_panel'
        elif 'cable' in url_lower or 'wire' in url_lower:
            return 'cable'
        return 'unknown'
    
    def _has_brand_logo(self, url: str) -> bool:
        brand_logos = ['deye', 'huawei', 'sma', 'fronius', 'kbe', 'longi']
        return any(logo in url.lower() for logo in brand_logos)

# ============================================
# 5. MULTI-MODAL FUSION
# ============================================

class MultiModalFusion:
    def __init__(self):
        self.text_analyzer = TextKIAnalyzer()
        self.image_analyzer = ImageKIAnalyzer()
    
    def analyze_product(self, row: pd.Series, with_images: bool = True) -> ProductAnalysis:
        # Text analysis
        text_result = self.text_analyzer.analyze(row)
        
        # Image analysis (if available)
        image_result = {'has_image': False, 'description': '', 'defects': []}
        if with_images and pd.notna(row.get('image_urls')):
            image_url = str(row['image_urls']).split('|')[0]
            image_result = self.image_analyzer.analyze_image(image_url)
        
        # Calculate overall quality score
        quality_score = self._calculate_quality_score(row, text_result, image_result)
        
        return ProductAnalysis(
            original_title=str(row.get('product_title', '')),
            detected_category=text_result['detected_category'],
            confidence_category=text_result['confidence_category'],
            extracted_brand=text_result['extracted_brand'],
            extracted_model=text_result['extracted_model'],
            extracted_power_kw=text_result['extracted_power_kw'],
            extracted_specs=text_result['extracted_specs'],
            has_defects=len(image_result.get('detected_defects', [])) > 0,
            image_description=image_result.get('description', ''),
            similar_products=[],  # Would use embedding similarity
            data_quality_score=quality_score,
            suggested_fixes=text_result['suggested_fixes']
        )

    def _calculate_quality_score(self, row: pd.Series, text_result: dict, image_result: dict) -> float:
        score = 0
        max_score = 10
        
        # Brand presence
        if text_result['extracted_brand'] != 'Unbekannt':
            score += 2
        
        # Image presence
        if image_result.get('has_image'):
            score += 2
        
        # Description
        if pd.notna(row.get('description')) and len(str(row['description'])) > 100:
            score += 2
        
        # Price
        if pd.notna(row.get('price')):
            score += 1
        
        # Category confidence
        score += text_result['confidence_category'] / 100
        
        return (score / max_score) * 100

# ============================================
# 6. PIPELINE ORCHESTRATION
# ============================================

class SolarProductPipeline:
    def __init__(self, api_key: Optional[str] = None):
        self.fusion = MultiModalFusion()
        self.api_key = api_key
    
    def process_batch(self, df: pd.DataFrame, max_workers: int = 4) -> pd.DataFrame:
        results = []
        total = len(df)
        
        print(f'Starting AI analysis of {total} products...')
        
        # Process in parallel
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(self._analyze_single, row): i 
                      for i, (_, row) in enumerate(df.iterrows())}
            
            for i, future in enumerate(as_completed(futures)):
                result = future.result()
                results.append(result)
                
                if (i + 1) % 100 == 0:
                    print(f'Processed {i+1}/{total} products ({(i+1)/total*100:.1f}%)')
        
        # Convert to DataFrame
        result_df = pd.DataFrame([{
            'original_title': r.original_title,
            'detected_category': r.detected_category,
            'category_confidence': r.confidence_category,
            'extracted_brand': r.extracted_brand,
            'extracted_model': r.extracted_model,
            'power_kw': r.extracted_power_kw,
            'image_description': r.image_description,
            'quality_score': r.data_quality_score,
            'suggested_fixes': '; '.join(r.suggested_fixes)
        } for r in results])
        
        return result_df
    
    def _analyze_single(self, row: pd.Series) -> ProductAnalysis:
        return self.fusion.analyze_product(row, with_images=True)

# ============================================
# 7. MAIN EXECUTION
# ============================================

if __name__ == '__main__':
    # Load data
    print('Loading product data...')
    dfs = []
    for name, path in [
        ('Sun Store', '/home/user/dashboard_app/sun_store_products_complete.csv'),
        ('Solidtrading', '/home/user/dashboard_app/solidtrading_products_complete.csv'),
        ('Tritec', '/home/user/dashboard_app/tritec_energy_products_complete.csv')
    ]:
        df = pd.read_csv(path)
        df['source'] = name
        dfs.append(df)
    
    combined = pd.concat(dfs).drop_duplicates(subset=['product_url'])
    print(f'Loaded {len(combined)} products')
    
    # Run pipeline (sample for demo)
    pipeline = SolarProductPipeline()
    
    sample_size = min(500, len(combined))  # Process sample for demo
    sample_df = combined.head(sample_size)
    
    print(f'Running AI analysis on {sample_size} products...')
    results = pipeline.process_batch(sample_df, max_workers=4)
    
    # Show results
    print('\n' + '='*60)
    print('KI-ANALYSE ERGEBNISSE')
    print('='*60)
    
    print('\n📊 Kategorie-Verteilung:')
    print(results['detected_category'].value_counts())
    
    print('\n🏆 Top Marken:')
    print(results['extracted_brand'].value_counts().head(10))
    
    print('\n📈 Datenqualität:')
    print(results['quality_score'].describe())
    
    # Save results
    results.to_csv('/home/user/dashboard_app/ai_analysis_results.csv', index=False)
    print('\n✅ Results saved to ai_analysis_results.csv')