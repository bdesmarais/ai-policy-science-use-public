"""
Press Release Analysis for WTG Letter of Inquiry
Analyzes California state legislators' press releases to identify education-related content
and compare patterns between Democratic and Republican legislators.

Author: Desmarais et al.
Date: December 2025

NOTE (repo adaptation, 2026): This is the original cloud-session analysis script,
lightly adapted to run from this repository. Changes vs. the verbatim original
(preserved as analyze_press_releases.cloud_original.py):
  - Data paths point to ../data/raw/ instead of /mnt/user-data/uploads/
  - Figures + processed CSV are written under the repo instead of /home/claude/
  - seaborn is now optional (it was only used for plot styling)
"""

import os
import pandas as pd
import matplotlib.pyplot as plt
from collections import Counter
import re
from datetime import datetime
import numpy as np

# Repo-relative paths (works regardless of current working directory)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data', 'raw')
FIG_DIR = os.path.join(BASE_DIR, 'figures')
PROC_DIR = os.path.join(BASE_DIR, 'data', 'processed')

# Set style for publication-quality figures (seaborn optional)
try:
    import seaborn as sns
    sns.set_palette("colorblind")
except ImportError:
    pass
try:
    plt.style.use('seaborn-v0_8-whitegrid')
except OSError:
    plt.style.use('ggplot')

# Define education-related keywords
EDUCATION_KEYWORDS = [
    'school', 'student', 'teacher', 'education', 'classroom', 'curriculum',
    'learning', 'college', 'university', 'k-12', 'k12', 'kindergarten',
    'elementary', 'middle school', 'high school', 'graduate', 'degree',
    'literacy', 'reading', 'math', 'stem', 'science education',
    'charter', 'public school', 'private school', 'tuition', 'scholarship',
    'sel', 'social-emotional', 'social emotional', 'mental health student',
    'school safety', 'campus', 'academic', 'textbook', 'homework',
    'graduation', 'dropout', 'truancy', 'attendance', 'school board',
    'superintendent', 'principal', 'faculty', 'professor', 'higher ed',
    'community college', 'uc ', 'csu ', 'cal state', 'prek', 'pre-k',
    'preschool', 'childcare', 'child care', 'early childhood',
    'special education', 'iep', 'title i', 'title ix', 'pell grant',
    'financial aid', 'student loan', 'fafsa', 'school funding',
    'school choice', 'voucher', 'homeschool', 'distance learning',
    'online learning', 'ed tech', 'edtech', 'classroom technology'
]

# Polarized education topics (2026 focus areas)
POLARIZED_TOPICS = {
    'SEL/Mental Health': ['social-emotional', 'social emotional', 'sel ', 'mental health', 
                          'counselor', 'anxiety', 'depression', 'suicide prevention',
                          'wellness', 'behavioral health', 'trauma-informed'],
    'School Safety': ['school safety', 'campus security', 'school resource officer',
                      'sro', 'gun violence', 'active shooter', 'lockdown', 'threat assessment',
                      'metal detector', 'surveillance', 'school police'],
    'Reading/Curriculum': ['reading', 'literacy', 'phonics', 'curriculum', 'textbook',
                           'book ban', 'library', 'critical race', 'crt', 'dei',
                           'history curriculum', 'science of reading', 'balanced literacy'],
    'School Choice': ['charter', 'voucher', 'school choice', 'private school', 'homeschool',
                      'parental rights', 'parent choice'],
    'EdTech/AI': ['artificial intelligence', ' ai ', 'edtech', 'ed tech', 'online learning',
                  'digital learning', 'technology in education', 'computer science',
                  'coding', 'chatgpt', 'machine learning']
}

def load_data():
    """Load Democratic and Republican press release data."""
    # Load Democratic data
    dem_df = pd.read_csv(os.path.join(DATA_DIR, 'Dem_assembly_press_09012025.csv'))
    dem_df['party'] = 'Democratic'

    # Load Republican data
    rep_df = pd.read_csv(os.path.join(DATA_DIR, 'Rep_asm_press_09052025.csv'))
    rep_df.columns = ['name', 'district', 'party_orig', 'title', 'link', 'date']
    rep_df['party'] = 'Republican'
    
    # Standardize columns
    dem_df = dem_df[['name', 'district', 'title', 'link', 'date', 'party']]
    rep_df = rep_df[['name', 'district', 'title', 'link', 'date', 'party']]
    
    return dem_df, rep_df

def is_education_related(title):
    """Check if a press release title is education-related."""
    if pd.isna(title):
        return False
    title_lower = title.lower()
    return any(kw in title_lower for kw in EDUCATION_KEYWORDS)

def categorize_polarized_topic(title):
    """Categorize press release into polarized education topics."""
    if pd.isna(title):
        return []
    title_lower = title.lower()
    topics = []
    for topic, keywords in POLARIZED_TOPICS.items():
        if any(kw in title_lower for kw in keywords):
            topics.append(topic)
    return topics

def parse_date(date_str):
    """Parse date string to datetime object."""
    if pd.isna(date_str):
        return None
    try:
        # Try different formats
        for fmt in ['%A, %B %d, %Y', '%B %d, %Y', '%Y-%m-%d']:
            try:
                return datetime.strptime(date_str.strip(), fmt)
            except ValueError:
                continue
        return None
    except:
        return None

def analyze_data(dem_df, rep_df):
    """Perform comprehensive analysis of press release data."""
    results = {}
    
    # Combine dataframes
    all_df = pd.concat([dem_df, rep_df], ignore_index=True)
    
    # Basic counts
    results['total_dem'] = len(dem_df)
    results['total_rep'] = len(rep_df)
    results['total_all'] = len(all_df)
    
    # Education-related filtering
    all_df['is_education'] = all_df['title'].apply(is_education_related)
    dem_edu = all_df[(all_df['party'] == 'Democratic') & (all_df['is_education'])]
    rep_edu = all_df[(all_df['party'] == 'Republican') & (all_df['is_education'])]
    
    results['edu_dem'] = len(dem_edu)
    results['edu_rep'] = len(rep_edu)
    results['edu_dem_pct'] = len(dem_edu) / len(dem_df) * 100
    results['edu_rep_pct'] = len(rep_edu) / len(rep_df) * 100
    
    # Polarized topic analysis
    all_df['polarized_topics'] = all_df['title'].apply(categorize_polarized_topic)
    
    topic_counts = {'Democratic': Counter(), 'Republican': Counter()}
    for _, row in all_df.iterrows():
        for topic in row['polarized_topics']:
            topic_counts[row['party']][topic] += 1
    
    results['topic_counts'] = topic_counts
    
    # Parse dates for temporal analysis
    all_df['parsed_date'] = all_df['date'].apply(parse_date)
    all_df['year'] = all_df['parsed_date'].apply(lambda x: x.year if x else None)
    
    # Year-by-year education counts
    edu_by_year = all_df[all_df['is_education']].groupby(['year', 'party']).size().unstack(fill_value=0)
    results['edu_by_year'] = edu_by_year
    
    # Store dataframes for visualization
    results['all_df'] = all_df
    results['dem_edu_df'] = dem_edu
    results['rep_edu_df'] = rep_edu
    
    return results

def create_visualizations(results, output_dir=None):
    """Generate publication-quality visualizations."""
    if output_dir is None:
        output_dir = FIG_DIR
    os.makedirs(output_dir, exist_ok=True)
    
    # Figure 1: Overall corpus composition
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    
    # Panel A: Total press releases by party
    parties = ['Democratic', 'Republican']
    totals = [results['total_dem'], results['total_rep']]
    colors = ['#2166AC', '#B2182B']  # Blue for Dem, Red for Rep
    
    bars = axes[0].bar(parties, totals, color=colors, edgecolor='black', linewidth=1.2)
    axes[0].set_ylabel('Number of Press Releases', fontsize=12)
    axes[0].set_title('A. Total Press Releases by Party', fontsize=14, fontweight='bold')
    axes[0].set_ylim(0, max(totals) * 1.15)
    
    # Add value labels
    for bar, val in zip(bars, totals):
        axes[0].text(bar.get_x() + bar.get_width()/2, bar.get_height() + 50, 
                    f'n={val:,}', ha='center', va='bottom', fontsize=11, fontweight='bold')
    
    # Panel B: Education-related press releases
    edu_counts = [results['edu_dem'], results['edu_rep']]
    edu_pcts = [results['edu_dem_pct'], results['edu_rep_pct']]
    
    bars = axes[1].bar(parties, edu_counts, color=colors, edgecolor='black', linewidth=1.2)
    axes[1].set_ylabel('Number of Education-Related Press Releases', fontsize=12)
    axes[1].set_title('B. Education-Related Press Releases', fontsize=14, fontweight='bold')
    axes[1].set_ylim(0, max(edu_counts) * 1.2)
    
    # Add value labels with percentages
    for bar, val, pct in zip(bars, edu_counts, edu_pcts):
        axes[1].text(bar.get_x() + bar.get_width()/2, bar.get_height() + 5, 
                    f'n={val}\n({pct:.1f}%)', ha='center', va='bottom', fontsize=10, fontweight='bold')
    
    plt.tight_layout()
    plt.savefig(f'{output_dir}/fig1_corpus_overview.png', dpi=300, bbox_inches='tight', 
                facecolor='white', edgecolor='none')
    plt.close()
    
    # Figure 2: Polarized topics comparison
    fig, ax = plt.subplots(figsize=(10, 6))
    
    topics = list(POLARIZED_TOPICS.keys())
    dem_counts = [results['topic_counts']['Democratic'][t] for t in topics]
    rep_counts = [results['topic_counts']['Republican'][t] for t in topics]
    
    x = np.arange(len(topics))
    width = 0.35
    
    bars1 = ax.bar(x - width/2, dem_counts, width, label='Democratic', color='#2166AC', 
                   edgecolor='black', linewidth=1)
    bars2 = ax.bar(x + width/2, rep_counts, width, label='Republican', color='#B2182B',
                   edgecolor='black', linewidth=1)
    
    ax.set_ylabel('Number of Press Releases', fontsize=12)
    ax.set_title('Press Releases by Polarized Education Topic', fontsize=14, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(topics, rotation=25, ha='right', fontsize=10)
    ax.legend(loc='upper right', fontsize=11)
    ax.set_ylim(0, max(max(dem_counts), max(rep_counts)) * 1.2)
    
    # Add value labels
    for bars in [bars1, bars2]:
        for bar in bars:
            height = bar.get_height()
            if height > 0:
                ax.text(bar.get_x() + bar.get_width()/2, height + 1, 
                       f'{int(height)}', ha='center', va='bottom', fontsize=9)
    
    plt.tight_layout()
    plt.savefig(f'{output_dir}/fig2_polarized_topics.png', dpi=300, bbox_inches='tight',
                facecolor='white', edgecolor='none')
    plt.close()
    
    # Figure 3: Temporal trends (if data available)
    if 'edu_by_year' in results and not results['edu_by_year'].empty:
        fig, ax = plt.subplots(figsize=(10, 6))
        
        edu_by_year = results['edu_by_year']
        # Filter to recent years with data
        recent_years = edu_by_year[edu_by_year.index >= 2020].copy()
        
        if not recent_years.empty:
            years = recent_years.index.astype(int)
            
            if 'Democratic' in recent_years.columns:
                ax.plot(years, recent_years['Democratic'], 'o-', color='#2166AC', 
                       linewidth=2.5, markersize=8, label='Democratic')
            if 'Republican' in recent_years.columns:
                ax.plot(years, recent_years['Republican'], 's-', color='#B2182B', 
                       linewidth=2.5, markersize=8, label='Republican')
            
            ax.set_xlabel('Year', fontsize=12)
            ax.set_ylabel('Number of Education-Related Press Releases', fontsize=12)
            ax.set_title('Temporal Trends in Education Policy Communication', 
                        fontsize=14, fontweight='bold')
            ax.legend(loc='upper left', fontsize=11)
            ax.set_xticks(years)
            
            plt.tight_layout()
            plt.savefig(f'{output_dir}/fig3_temporal_trends.png', dpi=300, bbox_inches='tight',
                        facecolor='white', edgecolor='none')
            plt.close()
    
    # Figure 4: Normalized comparison (rate per legislator or as percentage)
    fig, ax = plt.subplots(figsize=(8, 6))
    
    # Calculate percentages for each polarized topic
    topics = list(POLARIZED_TOPICS.keys())
    dem_pcts = [results['topic_counts']['Democratic'][t] / results['total_dem'] * 100 for t in topics]
    rep_pcts = [results['topic_counts']['Republican'][t] / results['total_rep'] * 100 for t in topics]
    
    x = np.arange(len(topics))
    width = 0.35
    
    bars1 = ax.bar(x - width/2, dem_pcts, width, label='Democratic', color='#2166AC',
                   edgecolor='black', linewidth=1)
    bars2 = ax.bar(x + width/2, rep_pcts, width, label='Republican', color='#B2182B',
                   edgecolor='black', linewidth=1)
    
    ax.set_ylabel('Percentage of Party\'s Press Releases (%)', fontsize=12)
    ax.set_title('Topic Emphasis by Party (Normalized)', fontsize=14, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(topics, rotation=25, ha='right', fontsize=10)
    ax.legend(loc='upper right', fontsize=11)
    
    plt.tight_layout()
    plt.savefig(f'{output_dir}/fig4_normalized_topics.png', dpi=300, bbox_inches='tight',
                facecolor='white', edgecolor='none')
    plt.close()
    
    print("All visualizations saved successfully!")

def extract_example_titles(results):
    """Extract example education-related titles for each party and topic."""
    examples = {'Democratic': {}, 'Republican': {}}
    
    all_df = results['all_df']
    
    for party in ['Democratic', 'Republican']:
        party_df = all_df[all_df['party'] == party]
        
        # General education examples
        edu_df = party_df[party_df['is_education']]
        if len(edu_df) > 0:
            examples[party]['General Education'] = edu_df['title'].head(5).tolist()
        
        # Topic-specific examples
        for topic in POLARIZED_TOPICS.keys():
            topic_df = party_df[party_df['polarized_topics'].apply(lambda x: topic in x)]
            if len(topic_df) > 0:
                examples[party][topic] = topic_df['title'].head(3).tolist()
    
    return examples

def generate_summary_statistics(results):
    """Generate summary statistics for the LOI."""
    summary = []
    summary.append("=" * 70)
    summary.append("PRESS RELEASE ANALYSIS SUMMARY")
    summary.append("California State Assembly Members")
    summary.append("=" * 70)
    summary.append("")
    summary.append("CORPUS OVERVIEW")
    summary.append("-" * 40)
    summary.append(f"Total Democratic Press Releases: {results['total_dem']:,}")
    summary.append(f"Total Republican Press Releases: {results['total_rep']:,}")
    summary.append(f"Combined Total: {results['total_all']:,}")
    summary.append("")
    summary.append("EDUCATION-RELATED CONTENT")
    summary.append("-" * 40)
    summary.append(f"Democratic Education Releases: {results['edu_dem']:,} ({results['edu_dem_pct']:.1f}%)")
    summary.append(f"Republican Education Releases: {results['edu_rep']:,} ({results['edu_rep_pct']:.1f}%)")
    summary.append("")
    summary.append("POLARIZED TOPICS BREAKDOWN")
    summary.append("-" * 40)
    
    for topic in POLARIZED_TOPICS.keys():
        dem_n = results['topic_counts']['Democratic'][topic]
        rep_n = results['topic_counts']['Republican'][topic]
        dem_pct = dem_n / results['total_dem'] * 100
        rep_pct = rep_n / results['total_rep'] * 100
        summary.append(f"{topic}:")
        summary.append(f"  Democratic: {dem_n} ({dem_pct:.2f}%)")
        summary.append(f"  Republican: {rep_n} ({rep_pct:.2f}%)")
    
    summary.append("")
    summary.append("=" * 70)
    
    return "\n".join(summary)

def main():
    """Main analysis pipeline."""
    print("Loading data...")
    dem_df, rep_df = load_data()
    
    print("Analyzing data...")
    results = analyze_data(dem_df, rep_df)
    
    print("Creating visualizations...")
    create_visualizations(results)
    
    print("Extracting examples...")
    examples = extract_example_titles(results)
    
    print("\n" + generate_summary_statistics(results))
    
    # Print example titles
    print("\nEXAMPLE EDUCATION-RELATED PRESS RELEASE TITLES")
    print("=" * 70)
    for party in ['Democratic', 'Republican']:
        print(f"\n{party.upper()} EXAMPLES:")
        print("-" * 40)
        for topic, titles in examples[party].items():
            if titles:
                print(f"\n{topic}:")
                for i, title in enumerate(titles[:2], 1):
                    print(f"  {i}. {title[:80]}{'...' if len(title) > 80 else ''}")
    
    # Save results to CSV for reference
    os.makedirs(PROC_DIR, exist_ok=True)
    out_csv = os.path.join(PROC_DIR, 'analyzed_press_releases.csv')
    results['all_df'].to_csv(out_csv, index=False)
    print(f"\nAnalyzed data saved to {out_csv}")
    
    return results

if __name__ == "__main__":
    results = main()
