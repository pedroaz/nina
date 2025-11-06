import { getBlogPostBySlug, getAllBlogPosts } from '@/lib/blog-data';
import { notFound } from 'next/navigation';
import Image from 'next/image';
import Link from 'next/link';
import { Button } from '@/components/shared/ui/button';

export async function generateStaticParams() {
  const posts = getAllBlogPosts();
  return posts.map((post) => ({
    slug: post.slug,
  }));
}

export default function BlogPostPage({
  params,
}: {
  params: { slug: string };
}) {
  const post = getBlogPostBySlug(params.slug);

  if (!post) {
    notFound();
  }

  return (
    <div className="w-full py-12 lg:py-16">
      <article className="container mx-auto max-w-4xl px-6">
        {/* Back button */}
        <Link href="/blog" className="inline-block mb-8">
          <Button variant="ghost" size="sm">
            ← Back to Blog
          </Button>
        </Link>

        {/* Featured image */}
        {post.images && post.images.length > 0 && (
          <div className="relative w-full h-[400px] mb-8 rounded-lg overflow-hidden">
            <Image
              src={post.images[0]}
              alt={post.title}
              fill
              className="object-cover"
            />
          </div>
        )}

        {/* Post header */}
        <header className="mb-8">
          <h1 className="text-4xl md:text-5xl font-bold font-display mb-4 text-black dark:text-white">
            {post.title}
          </h1>

          <div className="flex items-center gap-4 text-gray-600 dark:text-gray-400 mb-4">
            {post.author?.avatar && (
              <Image
                src={post.author.avatar}
                alt={post.author.name || 'Author'}
                width={40}
                height={40}
                className="rounded-full"
              />
            )}
            <div>
              {post.author?.name && (
                <div className="font-medium text-black dark:text-white">
                  {post.author.name}
                </div>
              )}
              <div className="text-sm">
                {post.date} • {post.readingTime} min read
              </div>
            </div>
          </div>

          {/* Tags */}
          {post.tags && post.tags.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {post.tags.map((tag, index) => {
                const tagText = typeof tag === 'string' ? tag : tag.text;
                return (
                  <span
                    key={tagText}
                    className="px-3 py-1 text-sm rounded-full bg-primary-100 dark:bg-primary-900/20 text-primary-700 dark:text-primary-300"
                  >
                    {tagText}
                  </span>
                );
              })}
            </div>
          )}
        </header>

        {/* Post content */}
        <div className="prose prose-lg dark:prose-invert max-w-none">
          {post.summary && (
            <p className="text-xl text-gray-700 dark:text-gray-300 leading-relaxed mb-8">
              {post.summary}
            </p>
          )}

          {/* Sample blog content */}
          <h2>The Future of Language Learning</h2>
          <p>
            Artificial intelligence is transforming how we approach language
            learning, making it more accessible, personalized, and effective
            than ever before. With Nina, you can practice German conversation
            anytime, anywhere, with an AI tutor that adapts to your learning
            style and pace.
          </p>

          <h2>Why AI-Powered Learning Works</h2>
          <p>
            Traditional language learning methods often lack the conversational
            practice that is crucial for fluency. Nina solves this by providing
            unlimited conversation practice in a comfortable, judgment-free
            environment. Our AI understands context, corrects mistakes gently,
            and adjusts difficulty based on your progress.
          </p>

          <h2>Key Benefits</h2>
          <ul>
            <li>
              <strong>24/7 Availability:</strong> Practice whenever inspiration
              strikes, no scheduling required
            </li>
            <li>
              <strong>Personalized Learning:</strong> AI adapts to your level
              and learning goals
            </li>
            <li>
              <strong>Immediate Feedback:</strong> Get corrections and
              suggestions in real-time
            </li>
            <li>
              <strong>Privacy-Focused:</strong> All data stays in Germany,
              GDPR compliant
            </li>
          </ul>

          <h2>Getting Started</h2>
          <p>
            Ready to experience the future of German learning? Start your free
            trial today and discover how AI can accelerate your path to fluency.
            No credit card required, and you can upgrade to unlimited access
            anytime.
          </p>
        </div>

        {/* CTA */}
        <div className="mt-12 pt-8 border-t border-gray-200 dark:border-gray-800">
          <div className="text-center">
            <h3 className="text-2xl font-bold mb-4 text-black dark:text-white">
              Ready to start learning?
            </h3>
            <p className="text-gray-600 dark:text-gray-400 mb-6">
              Try Nina today and experience AI-powered German learning.
            </p>
            <Button size="lg" variant="default" asChild>
              <a href="/">Start for Free</a>
            </Button>
          </div>
        </div>
      </article>
    </div>
  );
}
