import { BlogPost } from '@/components/landing/blog/LandingBlogPost';

export const blogPosts: BlogPost[] = [
  {
    slug: 'learning-german-with-ai',
    date: 'November 1, 2024',
    title: 'How AI is Revolutionizing German Language Learning',
    summary:
      'Discover how artificial intelligence is making German learning more interactive, personalized, and effective than ever before. Nina combines cutting-edge AI with proven language learning methods to help you achieve fluency faster.',
    tags: ['AI', 'German Learning', 'Education'],
    images: ['https://picsum.photos/id/180/800/600'],
    readingTime: 5,
    author: {
      name: 'Nina Team',
      avatar: 'https://picsum.photos/id/64/100/100',
    },
  },
];

export function getBlogPostBySlug(slug: string): BlogPost | undefined {
  return blogPosts.find((post) => post.slug === slug);
}

export function getAllBlogPosts(): BlogPost[] {
  return blogPosts;
}
