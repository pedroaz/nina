import { LandingBlogList } from '@/components/landing';
import { LandingBlogPost } from '@/components/landing/blog/LandingBlogPost';
import { getAllBlogPosts } from '@/lib/blog-data';

export default function BlogPage() {
  const blogPosts = getAllBlogPosts();

  return (
    <LandingBlogList
      title="Nina's German Learning Blog"
      description="Tips, insights, and stories about learning German with AI"
      display="grid"
      variant="primary"
      textPosition="center"
    >
      {blogPosts.map((post) => (
        <LandingBlogPost key={post.slug} post={post} imagePosition="right" />
      ))}
    </LandingBlogList>
  );
}
